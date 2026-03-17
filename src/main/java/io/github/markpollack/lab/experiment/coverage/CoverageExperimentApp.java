package io.github.markpollack.lab.experiment.coverage;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import io.github.markpollack.lab.experiment.coverage.dataset.SlugFilteringDatasetManager;
import io.github.markpollack.lab.experiment.coverage.judge.JuryFactory;
import io.github.markpollack.lab.experiment.coverage.judge.TestQualityJudge;
import ai.tuvium.experiment.dataset.DatasetManager;
import ai.tuvium.experiment.dataset.FileSystemDatasetManager;
import ai.tuvium.experiment.result.ExperimentResult;
import ai.tuvium.experiment.runner.ExperimentConfig;
import ai.tuvium.experiment.runner.ExperimentRunner;
import ai.tuvium.experiment.store.ActiveSession;
import ai.tuvium.experiment.store.FileSystemResultStore;
import ai.tuvium.experiment.store.FileSystemSessionStore;
import ai.tuvium.experiment.store.ResultStore;
import ai.tuvium.experiment.store.RunSessionStatus;
import ai.tuvium.experiment.store.SessionStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springaicommunity.judge.coverage.CoverageImprovementJudge;
import org.springaicommunity.judge.coverage.CoveragePreservationJudge;
import org.springaicommunity.judge.exec.BuildSuccessJudge;
import org.springaicommunity.judge.jury.Jury;
import org.springaicommunity.judge.jury.TierPolicy;
import org.yaml.snakeyaml.Yaml;

/**
 * Main experiment application for the Skills-vs-KB coverage experiment.
 * Reads variant configurations, iterates through each variant, and runs the
 * experiment loop via experiment-driver.
 */
public class CoverageExperimentApp {

	private static final Logger logger = LoggerFactory.getLogger(CoverageExperimentApp.class);

	private static final DateTimeFormatter SESSION_NAME_FORMAT =
			DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").withZone(ZoneOffset.UTC);

	private final ExperimentVariantConfig variantConfig;

	private final JuryFactory juryFactory;

	private final ResultStore resultStore;

	private final SessionStore sessionStore;

	private final Path projectRoot;

	public CoverageExperimentApp(ExperimentVariantConfig variantConfig, JuryFactory juryFactory,
			ResultStore resultStore, SessionStore sessionStore, Path projectRoot) {
		this.variantConfig = variantConfig;
		this.juryFactory = juryFactory;
		this.resultStore = resultStore;
		this.sessionStore = sessionStore;
		this.projectRoot = projectRoot;
	}

	public ExperimentResult runVariant(VariantSpec variant, String sessionName) {
		logger.info("Running variant: {} (session: {})", variant.name(), sessionName);

		Jury jury = juryFactory.build(variant);
		AbstractCoverageAgentInvoker invoker = createInvoker(variant);

		String model = variant.model() != null ? variant.model() : variantConfig.defaultModel();

		ExperimentConfig config = ExperimentConfig.builder()
			.experimentName(variantConfig.experimentName())
			.datasetDir(projectRoot.resolve("datasets"))
			.promptTemplate(loadPromptFile(variant.promptFile()))
			.model(model)
			.perItemTimeout(Duration.ofMinutes(variantConfig.timeoutMinutes()))
			.knowledgeBaseDir(variant.knowledgeDir() != null ? projectRoot.resolve(variant.knowledgeDir()) : null)
			.preserveWorkspaces(true)
			.outputDir(projectRoot.resolve("results"))
			.build();

		DatasetManager datasetManager = variantConfig.itemSlugFilter() != null
				? new SlugFilteringDatasetManager(variantConfig.datasetManager(), variantConfig.itemSlugFilter())
				: variantConfig.datasetManager();

		ExperimentRunner runner = new ExperimentRunner(datasetManager, jury, resultStore, sessionStore, config);
		ActiveSession activeSession = new ActiveSession(sessionName, variantConfig.experimentName(), variant.name());
		ExperimentResult result = runner.run(invoker, activeSession);

		logger.info("========================================");
		logger.info("  VARIANT '{}' COMPLETE", variant.name());
		logger.info("  Pass rate: {}", String.format("%.1f%%", result.passRate() * 100));
		logger.info("  Cost: ${}", String.format("%.4f", result.totalCostUsd()));
		logger.info("  Duration: {}s", result.totalDurationMs() / 1000);
		logger.info("========================================");

		return result;
	}

	public void runAllVariants() {
		List<VariantSpec> variants = variantConfig.variants();
		String sessionName = SESSION_NAME_FORMAT.format(Instant.now());

		logger.info("Running {} variants for experiment '{}' (session: {})",
				variants.size(), variantConfig.experimentName(), sessionName);

		sessionStore.createSession(sessionName, variantConfig.experimentName(), Map.of());
		try {
			for (VariantSpec variant : variants) {
				runVariant(variant, sessionName);
			}
			sessionStore.finalizeSession(sessionName, variantConfig.experimentName(), RunSessionStatus.COMPLETED);
		}
		catch (Exception ex) {
			sessionStore.finalizeSession(sessionName, variantConfig.experimentName(), RunSessionStatus.FAILED);
			throw ex;
		}
	}

	AbstractCoverageAgentInvoker createInvoker(VariantSpec variant) {
		Path knowledgeSourceDir = variant.knowledgeDir() != null
				? projectRoot.resolve(variant.knowledgeDir()) : null;
		List<String> knowledgeFiles = variant.knowledgeFiles();
		boolean hasKnowledge = knowledgeSourceDir != null && !knowledgeFiles.isEmpty();

		if (variant.actPromptFile() != null) {
			String actPrompt = loadPromptFile(variant.actPromptFile());
			return new TwoPhaseCoverageInvoker(
					hasKnowledge ? knowledgeSourceDir : null,
					hasKnowledge ? knowledgeFiles : null,
					variant.skillsInstall(),
					actPrompt);
		}

		return new SinglePhaseCoverageInvoker(
				hasKnowledge ? knowledgeSourceDir : null,
				hasKnowledge ? knowledgeFiles : null,
				variant.skillsInstall());
	}

	private String loadPromptFile(String promptFileName) {
		Path promptPath = projectRoot.resolve(promptFileName);
		try {
			return Files.readString(promptPath);
		}
		catch (IOException ex) {
			throw new UncheckedIOException("Failed to load prompt: " + promptPath, ex);
		}
	}

	@SuppressWarnings("unchecked")
	static ExperimentVariantConfig loadConfig(Path configPath) {
		Yaml yaml = new Yaml();
		Map<String, Object> raw;
		try (InputStream in = Files.newInputStream(configPath)) {
			raw = yaml.load(in);
		}
		catch (IOException ex) {
			throw new UncheckedIOException("Failed to load config: " + configPath, ex);
		}

		String experimentName = (String) raw.get("experimentName");
		String defaultModel = (String) raw.get("defaultModel");
		int timeoutMinutes = (int) raw.get("timeoutMinutes");

		List<Map<String, Object>> rawVariants = (List<Map<String, Object>>) raw.get("variants");
		List<VariantSpec> variants = new ArrayList<>();
		for (Map<String, Object> rv : rawVariants) {
			String name = (String) rv.get("name");
			String promptFile = (String) rv.get("promptFile");
			String actPromptFile = (String) rv.get("actPromptFile");
			String knowledgeDir = (String) rv.get("knowledgeDir");
			List<String> knowledgeFiles = rv.get("knowledgeFiles") != null
					? (List<String>) rv.get("knowledgeFiles") : List.of();
			Map<String, String> judgeOverrides = rv.get("judgeOverrides") != null
					? (Map<String, String>) rv.get("judgeOverrides") : null;
			String model = (String) rv.get("model");
			boolean skillsInstall = Boolean.TRUE.equals(rv.get("skillsInstall"));
			variants.add(new VariantSpec(name, promptFile, actPromptFile, knowledgeDir,
					knowledgeFiles, judgeOverrides, model, skillsInstall));
		}

		return new ExperimentVariantConfig(
				experimentName, defaultModel, timeoutMinutes,
				List.copyOf(variants), new FileSystemDatasetManager());
	}

	static JuryFactory buildJuryFactory(Path projectRoot) {
		Path judgePromptPath = projectRoot.resolve("plans/prompts/judge-practice-adherence.txt");
		logPromptHash(judgePromptPath);
		return JuryFactory.builder()
			.addJudge(0, BuildSuccessJudge.maven("clean", "test"))
			.tierPolicy(0, TierPolicy.REJECT_ON_ANY_FAIL)
			.addJudge(1, new CoveragePreservationJudge())
			.tierPolicy(1, TierPolicy.REJECT_ON_ANY_FAIL)
			.addJudge(2, new CoverageImprovementJudge(50.0, 80.0))
			.tierPolicy(2, TierPolicy.ACCEPT_ON_ALL_PASS)
			.addJudge(3, new TestQualityJudge(
					TestQualityJudge.defaultAgentClientFactory("claude-sonnet-4-6", Duration.ofMinutes(3)),
					judgePromptPath))
			.tierPolicy(3, TierPolicy.FINAL_TIER)
			.build();
	}

	private static void logPromptHash(Path promptPath) {
		try {
			byte[] bytes = Files.readAllBytes(promptPath);
			java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-256");
			byte[] hash = md.digest(bytes);
			StringBuilder hex = new StringBuilder();
			for (byte b : hash) hex.append(String.format("%02x", b));
			logger.info("T3 judge prompt SHA-256: {} ({})", hex.substring(0, 16), promptPath.getFileName());
		}
		catch (Exception ex) {
			logger.warn("Could not hash T3 judge prompt: {}", ex.getMessage());
		}
	}

	/**
	 * Main entry point.
	 * <pre>
	 *   ./mvnw compile exec:java -Dexec.args="--variant v1-simple"
	 *   ./mvnw compile exec:java -Dexec.args="--variant v1-simple --item gs-rest-service"
	 *   ./mvnw compile exec:java -Dexec.args="--run-all-variants"
	 * </pre>
	 */
	public static void main(String[] args) {
		System.setProperty("java.net.preferIPv4Stack", "true");

		Path projectRoot = Path.of(System.getProperty("user.dir"));
		String targetVariant = null;
		String targetItem = null;
		boolean runAll = false;

		for (int i = 0; i < args.length; i++) {
			switch (args[i]) {
				case "--variant" -> {
					if (i + 1 >= args.length) { logger.error("--variant requires a name"); System.exit(1); }
					targetVariant = args[++i];
				}
				case "--item" -> {
					if (i + 1 >= args.length) { logger.error("--item requires a slug"); System.exit(1); }
					targetItem = args[++i];
				}
				case "--run-all-variants" -> runAll = true;
				case "--project-root" -> {
					if (i + 1 >= args.length) { logger.error("--project-root requires a path"); System.exit(1); }
					projectRoot = Path.of(args[++i]);
				}
				default -> { logger.error("Unknown argument: {}", args[i]); System.exit(1); }
			}
		}

		if (targetVariant == null && !runAll) {
			logger.error("Usage: --variant <name> | --run-all-variants [--item <slug>]");
			System.exit(1);
		}

		ExperimentVariantConfig variantConfig = loadConfig(projectRoot.resolve("experiment-config.yaml"));

		if (targetItem != null) {
			variantConfig = variantConfig.withItemFilter(targetItem);
			logger.info("Filtering to single item: {}", targetItem);
		}

		logger.info("Loaded experiment '{}' with {} variants (model={}, timeout={}min)",
				variantConfig.experimentName(), variantConfig.variants().size(),
				variantConfig.defaultModel(), variantConfig.timeoutMinutes());

		Path resultsDir = projectRoot.resolve("results");
		ResultStore resultStore = new FileSystemResultStore(resultsDir);
		SessionStore sessionStore = new FileSystemSessionStore(resultsDir);
		JuryFactory juryFactory = buildJuryFactory(projectRoot);

		final ExperimentVariantConfig finalConfig = variantConfig;
		CoverageExperimentApp app = new CoverageExperimentApp(
				finalConfig, juryFactory, resultStore, sessionStore, projectRoot);

		if (runAll) {
			app.runAllVariants();
		}
		else {
			String variantName = targetVariant;
			VariantSpec variant = finalConfig.variants().stream()
				.filter(v -> v.name().equals(variantName))
				.findFirst()
				.orElseThrow(() -> new IllegalArgumentException(
						"Unknown variant: " + variantName + ". Available: "
								+ finalConfig.variants().stream().map(VariantSpec::name).toList()));

			String sessionName = SESSION_NAME_FORMAT.format(Instant.now());
			sessionStore.createSession(sessionName, finalConfig.experimentName(), Map.of());
			try {
				app.runVariant(variant, sessionName);
				sessionStore.finalizeSession(sessionName, finalConfig.experimentName(), RunSessionStatus.COMPLETED);
			}
			catch (Exception ex) {
				sessionStore.finalizeSession(sessionName, finalConfig.experimentName(), RunSessionStatus.FAILED);
				throw ex;
			}
		}
	}

}
