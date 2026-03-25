package io.github.markpollack.lab.experiment.coverage;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import io.github.markpollack.experiment.agent.AgentInvocationException;
import io.github.markpollack.experiment.agent.AgentInvoker;
import io.github.markpollack.experiment.agent.InvocationContext;
import io.github.markpollack.experiment.agent.InvocationResult;
import io.github.markpollack.journal.claude.PhaseCapture;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.lang.Nullable;
import org.springaicommunity.judge.coverage.JaCoCoReportParser;
import org.springaicommunity.judge.coverage.JaCoCoReportParser.CoverageMetrics;
import org.springaicommunity.judge.exec.util.MavenBuildRunner;
import org.springaicommunity.judge.exec.util.MavenBuildRunner.BuildResult;

/**
 * Base class for coverage agent invokers. Provides the shared workflow:
 * compile → JaCoCo → baseline → skills install → KB copy → [agent] → coverage → skills uninstall.
 *
 * <p>Subclasses implement {@link #invokeAgent} to define the invocation strategy.
 */
public abstract class AbstractCoverageAgentInvoker implements AgentInvoker {

	private static final Logger logger = LoggerFactory.getLogger(AbstractCoverageAgentInvoker.class);

	@Nullable
	private final Path knowledgeSourceDir;

	@Nullable
	private final List<String> knowledgeFiles;

	private final boolean skillsInstall;

	private final SkillsInstaller skillsInstaller;

	protected AbstractCoverageAgentInvoker(
			@Nullable Path knowledgeSourceDir,
			@Nullable List<String> knowledgeFiles,
			boolean skillsInstall) {
		this.knowledgeSourceDir = knowledgeSourceDir;
		this.knowledgeFiles = knowledgeFiles;
		this.skillsInstall = skillsInstall;
		this.skillsInstaller = new SkillsInstaller();
	}

	@Override
	public final InvocationResult invoke(InvocationContext context) throws AgentInvocationException {
		long startTime = System.currentTimeMillis();
		Path workspace = context.workspacePath();

		String itemSlug = context.metadata().getOrDefault("itemId", workspace.getFileName().toString());
		logger.info("=== Coverage Agent: {} ===", itemSlug);

		// 1. Verify baseline builds
		logger.info("Step 1: Verifying project compiles");
		BuildResult compileResult = MavenBuildRunner.runBuild(workspace, 5, "clean", "compile",
				"-Dspring-javaformat.skip=true", "-Dcheckstyle.skip=true");
		if (!compileResult.success()) {
			return InvocationResult.error("Project does not compile: " + compileResult.output(),
					context.metadata());
		}

		// 1b. Generate pre-analysis report (ProjectAnalyzer — regex-based structural scan)
		ProjectAnalyzer.analyze(workspace);

		// 2. Ensure JaCoCo plugin
		ensureJaCoCoPlugin(workspace);

		// 3. Measure baseline coverage
		CoverageMetrics baseline;
		if (hasTestFiles(workspace)) {
			logger.info("Step 3: Measuring baseline coverage");
			baseline = measureCoverage(workspace);
			logger.info("Baseline coverage: line={}%, branch={}%",
					baseline.lineCoverage(), baseline.branchCoverage());
		}
		else {
			logger.info("Step 3: No test files found — baseline is 0%");
			baseline = new CoverageMetrics(0.0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, "No tests");
		}

		// 4. Install skills (variants 4-6)
		boolean skillsWereInstalled = false;
		if (skillsInstall) {
			logger.info("Step 4a: Installing spring-testing-skills");
			skillsInstaller.install();
			if (!skillsInstaller.isInstalled()) {
				throw new IllegalStateException(
						"Skills installation reported success but no skill directories found in ~/.claude/skills/. "
								+ "Check SkillsInstaller logs above. Aborting to avoid running agent without skills.");
			}
			Path skillsDir = Path.of(System.getProperty("user.home"), ".claude", "skills");
			try (var stream = Files.list(skillsDir)) {
				stream.map(p -> p.getFileName().toString())
						.sorted()
						.forEach(name -> logger.info("Step 4b: Installed skill: {}", name));
			} catch (IOException e) {
				logger.warn("Step 4b: Could not list skills dir: {}", e.getMessage());
			}
			skillsWereInstalled = true;
		}

		// 5. Copy knowledge files into workspace
		copyKnowledge(workspace);

		// 6. Invoke agent (subclass-specific)
		AgentResult agentResult;
		try {
			agentResult = invokeAgent(context, baseline);
		}
		catch (Exception ex) {
			logger.error("Agent execution failed", ex);
			agentResult = new AgentResult(List.of(), null);
		}
		finally {
			// 7. Uninstall skills — always clean up, even on failure
			if (skillsWereInstalled) {
				logger.info("Step 7: Uninstalling spring-testing-skills");
				skillsInstaller.uninstall();
			}
		}

		// 8. Measure final coverage
		logger.info("Measuring final coverage");
		CoverageMetrics finalCov = measureCoverage(workspace);
		double improvement = finalCov.lineCoverage() - baseline.lineCoverage();
		logger.info("Final coverage: line={}%, branch={}% (improvement: {}pp)",
				finalCov.lineCoverage(), finalCov.branchCoverage(), improvement);

		long durationMs = System.currentTimeMillis() - startTime;

		Path jacocoReport = workspace.resolve("target/site/jacoco/jacoco.xml");
		boolean jacocoReportExists = Files.isRegularFile(jacocoReport);

		Map<String, String> enrichedMetadata = new HashMap<>(context.metadata());
		enrichedMetadata.put("baselineCoverage", String.valueOf(baseline.lineCoverage()));
		enrichedMetadata.put("finalCoverage", String.valueOf(finalCov.lineCoverage()));
		enrichedMetadata.put("baselineBranchCoverage", String.valueOf(baseline.branchCoverage()));
		enrichedMetadata.put("finalBranchCoverage", String.valueOf(finalCov.branchCoverage()));
		enrichedMetadata.put("coverageImprovement", String.valueOf(improvement));
		enrichedMetadata.put("skillsInstalled", String.valueOf(skillsInstall));
		enrichedMetadata.put("jacocoReportRelPath", "target/site/jacoco/jacoco.xml");
		enrichedMetadata.put("jacocoReportExists", String.valueOf(jacocoReportExists));

		return InvocationResult.fromPhases(agentResult.phases(), durationMs,
				agentResult.sessionId(), enrichedMetadata);
	}

	protected abstract AgentResult invokeAgent(InvocationContext context, CoverageMetrics baseline)
			throws Exception;

	protected String buildPrompt(String basePrompt, CoverageMetrics baseline) {
		StringBuilder sb = new StringBuilder(basePrompt);
		if (baseline.lineCoverage() == 0.0 && baseline.linesTotal() == 0) {
			sb.append("\n\n## Current State\n");
			sb.append("No tests exist yet. Coverage is 0%.\n");
			sb.append("JaCoCo is already configured. Run `./mvnw clean test jacoco:report` to generate reports.\n");
		}
		else {
			sb.append("\n\n## Current Coverage Metrics\n");
			sb.append("- Line coverage: ").append(String.format("%.1f", baseline.lineCoverage())).append("%\n");
			sb.append("- Branch coverage: ").append(String.format("%.1f", baseline.branchCoverage())).append("%\n");
			sb.append("- Lines covered: ").append(baseline.linesCovered())
					.append("/").append(baseline.linesTotal()).append("\n");
			sb.append("\nNote: JaCoCo is already configured. Run `./mvnw clean test jacoco:report` to regenerate.\n");
		}
		return sb.toString();
	}

	void copyKnowledge(Path workspace) {
		if (knowledgeSourceDir == null || knowledgeFiles == null || knowledgeFiles.isEmpty()) {
			return;
		}

		Path targetDir = workspace.resolve("knowledge");

		if (knowledgeFiles.contains("index.md")) {
			logger.info("Step 5: Copying full knowledge tree from {}", knowledgeSourceDir);
			copyDirectoryRecursively(knowledgeSourceDir, targetDir);
		}
		else {
			logger.info("Step 5: Copying {} targeted knowledge files", knowledgeFiles.size());
			for (String relativePath : knowledgeFiles) {
				Path source = knowledgeSourceDir.resolve(relativePath);
				Path target = targetDir.resolve(relativePath);
				try {
					Files.createDirectories(target.getParent());
					Files.copy(source, target, StandardCopyOption.REPLACE_EXISTING);
				}
				catch (IOException ex) {
					throw new UncheckedIOException("Failed to copy knowledge file: " + relativePath, ex);
				}
			}
		}
	}

	// Excludes application bootstrap classes (main() methods) which agents must not test.
	// Pattern matches *Application.java and *Main.java anywhere in the package tree.
	private static final String JACOCO_PLUGIN_SNIPPET = """
			<plugin>
				<groupId>org.jacoco</groupId>
				<artifactId>jacoco-maven-plugin</artifactId>
				<version>0.8.14</version>
				<configuration>
					<excludes>
						<exclude>**/*Application.class</exclude>
						<exclude>**/*Main.class</exclude>
					</excludes>
				</configuration>
				<executions>
					<execution>
						<id>default</id>
						<goals><goal>prepare-agent</goal></goals>
					</execution>
					<execution>
						<id>report</id>
						<phase>test</phase>
						<goals><goal>report</goal></goals>
					</execution>
				</executions>
			</plugin>
			""";

	void ensureJaCoCoPlugin(Path workspace) {
		Path pomPath = workspace.resolve("pom.xml");
		if (!Files.isRegularFile(pomPath)) {
			logger.warn("No pom.xml found in workspace — skipping JaCoCo injection");
			return;
		}
		try {
			String pom = Files.readString(pomPath);
			if (pom.contains("jacoco-maven-plugin")) {
				logger.info("Step 2: JaCoCo plugin already present");
				return;
			}
			logger.info("Step 2: Injecting JaCoCo plugin into pom.xml");
			String updated;
			if (pom.contains("</plugins>")) {
				updated = pom.replace("</plugins>", JACOCO_PLUGIN_SNIPPET + "    </plugins>");
			}
			else if (pom.contains("</build>")) {
				updated = pom.replace("</build>",
						"    <plugins>\n" + JACOCO_PLUGIN_SNIPPET + "    </plugins>\n  </build>");
			}
			else {
				updated = pom.replace("</project>",
						"  <build>\n    <plugins>\n" + JACOCO_PLUGIN_SNIPPET + "    </plugins>\n  </build>\n</project>");
			}
			Files.writeString(pomPath, updated);
		}
		catch (IOException ex) {
			throw new UncheckedIOException("Failed to inject JaCoCo plugin", ex);
		}
	}

	boolean hasTestFiles(Path workspace) {
		Path testJavaDir = workspace.resolve("src/test/java");
		if (!Files.isDirectory(testJavaDir)) return false;
		try (var stream = Files.walk(testJavaDir)) {
			return stream.anyMatch(p -> p.toString().endsWith(".java"));
		}
		catch (IOException ex) {
			return false;
		}
	}

	protected CoverageMetrics measureCoverage(Path workspace) {
		BuildResult result = MavenBuildRunner.runBuild(workspace, 10, "clean", "test", "jacoco:report",
				"-Dspring-javaformat.skip=true", "-Dcheckstyle.skip=true");
		if (result.success()) {
			return JaCoCoReportParser.parse(workspace);
		}
		logger.warn("Test execution failed during coverage measurement: {}",
				result.output().substring(0, Math.min(500, result.output().length())));
		return new CoverageMetrics(0.0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, "Tests failed");
	}

	private void copyDirectoryRecursively(Path source, Path target) {
		try {
			Files.walkFileTree(source, new SimpleFileVisitor<>() {
				@Override
				public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
					Files.createDirectories(target.resolve(source.relativize(dir)));
					return FileVisitResult.CONTINUE;
				}

				@Override
				public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
					Files.copy(file, target.resolve(source.relativize(file)), StandardCopyOption.REPLACE_EXISTING);
					return FileVisitResult.CONTINUE;
				}
			});
		}
		catch (IOException ex) {
			throw new UncheckedIOException("Failed to copy knowledge directory: " + source, ex);
		}
	}

	protected record AgentResult(List<PhaseCapture> phases, @Nullable String sessionId) {}

}
