package io.github.markpollack.lab.experiment.coverage;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Installs and uninstalls spring-testing-skills to/from ~/.claude/skills/,
 * using the com.skillsjars:maven-plugin:extract goal.
 *
 * <p>Install:
 * <ol>
 *   <li>Runs {@code mvn install} in the spring-testing-skills source project.</li>
 *   <li>Writes a minimal pom with spring-testing-skills as a plugin dependency,
 *       then runs {@code skillsjars:extract -Ddir=~/.claude/skills}.</li>
 * </ol>
 *
 * <p>Uninstall: removes all {@code skillsjars__spring-ai-community__spring-testing-skills__*}
 * directories from {@code ~/.claude/skills/}.
 */
public class SkillsInstaller {

	private static final Logger logger = LoggerFactory.getLogger(SkillsInstaller.class);

	private static final Path SKILLS_SOURCE = Path.of(System.getProperty("user.home"),
			"community", "spring-testing-skills");

	private static final Path SKILLS_INSTALL_DIR = Path.of(System.getProperty("user.home"),
			".claude", "skills");

	private static final String SKILLS_DIR_GLOB =
			"skillsjars__spring-ai-community__spring-testing-skills__*";

	private static final String EXTRACT_POM_TEMPLATE = """
			<?xml version="1.0" encoding="UTF-8"?>
			<project>
			  <modelVersion>4.0.0</modelVersion>
			  <groupId>ai.tuvium</groupId>
			  <artifactId>skills-extractor</artifactId>
			  <version>1.0</version>
			  <build>
			    <plugins>
			      <plugin>
			        <groupId>com.skillsjars</groupId>
			        <artifactId>maven-plugin</artifactId>
			        <version>0.0.6</version>
			        <dependencies>
			          <dependency>
			            <groupId>org.springaicommunity</groupId>
			            <artifactId>spring-testing-skills</artifactId>
			            <version>%s</version>
			          </dependency>
			        </dependencies>
			      </plugin>
			    </plugins>
			  </build>
			</project>
			""";

	public void install() {
		if (!Files.isDirectory(SKILLS_SOURCE)) {
			throw new IllegalStateException(
					"spring-testing-skills source not found: " + SKILLS_SOURCE +
					"\nClone it to ~/community/spring-testing-skills/");
		}

		// Step 1: build and install to local Maven repo
		logger.info("Building and installing spring-testing-skills from {}", SKILLS_SOURCE);
		runMaven(SKILLS_SOURCE, "install", "-q");

		// Step 2: write temp extract pom and run skillsjars:extract
		String version = readSkillsVersion();
		logger.info("Extracting spring-testing-skills {} to {}", version, SKILLS_INSTALL_DIR);
		try {
			Path tempPom = Files.createTempFile("skills-extract-", ".xml");
			Files.writeString(tempPom, EXTRACT_POM_TEMPLATE.formatted(version));
			tempPom.toFile().deleteOnExit();
			runMaven(tempPom.getParent(),
					"com.skillsjars:maven-plugin:0.0.6:extract",
					"-Ddir=" + SKILLS_INSTALL_DIR,
					"-f", tempPom.toString(),
					"-q");
		}
		catch (IOException ex) {
			throw new UncheckedIOException("Failed to write temp extract pom", ex);
		}

		if (!isInstalled()) {
			throw new IllegalStateException(
					"Skills extract ran but no skill directories found in: " + SKILLS_INSTALL_DIR);
		}
		logger.info("Skills installed: {}", SKILLS_INSTALL_DIR);
	}

	public void uninstall() {
		if (!Files.isDirectory(SKILLS_INSTALL_DIR)) {
			logger.debug("Skills install directory not found, nothing to uninstall");
			return;
		}
		logger.info("Uninstalling spring-testing-skills from {}", SKILLS_INSTALL_DIR);
		try (DirectoryStream<Path> stream = Files.newDirectoryStream(SKILLS_INSTALL_DIR, SKILLS_DIR_GLOB)) {
			for (Path skillDir : stream) {
				deleteRecursively(skillDir);
				logger.debug("Removed: {}", skillDir.getFileName());
			}
		}
		catch (IOException ex) {
			throw new UncheckedIOException("Failed to uninstall skills", ex);
		}
		logger.info("Skills uninstalled");
	}

	public boolean isInstalled() {
		if (!Files.isDirectory(SKILLS_INSTALL_DIR)) return false;
		try (DirectoryStream<Path> stream = Files.newDirectoryStream(SKILLS_INSTALL_DIR, SKILLS_DIR_GLOB)) {
			return stream.iterator().hasNext();
		}
		catch (IOException ex) {
			return false;
		}
	}

	public Path skillsInstallDir() {
		return SKILLS_INSTALL_DIR;
	}

	private String readSkillsVersion() {
		Path pomPath = SKILLS_SOURCE.resolve("pom.xml");
		try {
			String pom = Files.readString(pomPath);
			int idx = pom.indexOf("<artifactId>spring-testing-skills</artifactId>");
			if (idx >= 0) {
				int vStart = pom.indexOf("<version>", idx) + "<version>".length();
				int vEnd = pom.indexOf("</version>", vStart);
				if (vStart > 0 && vEnd > vStart) {
					return pom.substring(vStart, vEnd).trim();
				}
			}
			throw new IllegalStateException("Could not parse version from " + pomPath);
		}
		catch (IOException ex) {
			throw new UncheckedIOException("Failed to read " + pomPath, ex);
		}
	}

	/** Runs Maven using {@code mvnw} wrapper if present in workDir, otherwise falls back to {@code mvn}. */
	private void runMaven(Path workDir, String... args) {
		boolean isWindows = System.getProperty("os.name", "").toLowerCase().contains("win");
		String mvnw = isWindows ? "mvnw.cmd" : "./mvnw";
		boolean wrapperExists = workDir.resolve(isWindows ? "mvnw.cmd" : "mvnw").toFile().exists();
		String executable = wrapperExists ? mvnw : (isWindows ? "mvn.cmd" : "mvn");

		String[] command = new String[args.length + 1];
		command[0] = executable;
		System.arraycopy(args, 0, command, 1, args.length);
		try {
			int exitCode = new ProcessBuilder(command)
					.directory(workDir.toFile())
					.inheritIO()
					.start()
					.waitFor();
			if (exitCode != 0) {
				throw new IllegalStateException(
						String.join(" ", command) + " failed with exit code " + exitCode);
			}
		}
		catch (IOException ex) {
			throw new UncheckedIOException("Failed to run: " + String.join(" ", command), ex);
		}
		catch (InterruptedException ex) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("Process interrupted: " + String.join(" ", command), ex);
		}
	}

	private void deleteRecursively(Path path) throws IOException {
		try (var stream = Files.walk(path)) {
			stream.sorted(java.util.Comparator.reverseOrder())
					.forEach(p -> {
						try { Files.delete(p); }
						catch (IOException ex) { throw new UncheckedIOException(ex); }
					});
		}
	}

}
