package ai.tuvium.coverage;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;

import ai.tuvium.coverage.judge.TestQualityJudge;
import ai.tuvium.experiment.scoring.VerdictExtractor;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.databind.ser.std.StdSerializer;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springaicommunity.judge.context.ExecutionStatus;
import org.springaicommunity.judge.context.JudgmentContext;
import org.springaicommunity.judge.coverage.CoverageImprovementJudge;
import org.springaicommunity.judge.coverage.CoveragePreservationJudge;
import org.springaicommunity.judge.exec.BuildSuccessJudge;
import org.springaicommunity.judge.exec.util.MavenBuildRunner;
import org.springaicommunity.judge.jury.CascadedJury;
import org.springaicommunity.judge.jury.ConsensusStrategy;
import org.springaicommunity.judge.jury.Jury;
import org.springaicommunity.judge.jury.SimpleJury;
import org.springaicommunity.judge.jury.TierPolicy;
import org.springaicommunity.judge.jury.Verdict;
import org.springaicommunity.judge.score.BooleanScore;
import org.springaicommunity.judge.score.CategoricalScore;
import org.springaicommunity.judge.score.NumericalScore;
import org.springaicommunity.judge.score.Score;

/**
 * Re-run judges against preserved workspaces without re-invoking the agent.
 *
 * <p>Updates result JSON files in-place, preserving all original agent execution data.
 * Only the scores, verdict, and passed fields are rewritten.
 *
 * <pre>
 *   # Re-judge all valid sessions (T1+T2+T3)
 *   ./mvnw compile exec:java -Dexec.mainClass=ai.tuvium.coverage.RejudgeApp \
 *     -Dexec.args="--regenerate-jacoco"
 *
 *   # Coverage judges only (fast, no LLM calls)
 *   ./mvnw compile exec:java -Dexec.mainClass=ai.tuvium.coverage.RejudgeApp \
 *     -Dexec.args="--tiers 1,2 --regenerate-jacoco"
 *
 *   # Single session, dry-run
 *   ./mvnw compile exec:java -Dexec.mainClass=ai.tuvium.coverage.RejudgeApp \
 *     -Dexec.args="--session 20260312-181643 --dry-run"
 * </pre>
 */
public class RejudgeApp {

	private static final Logger logger = LoggerFactory.getLogger(RejudgeApp.class);

	// The 20 valid sessions used in the Markov analysis (curated r1 + N=3 sweep).
	// Excludes early exploration sessions ($0.40 runs) and the forge timeout.
	private static final List<String> VALID_SESSIONS = List.of(
			"20260312-181643",  // simple r1
			"20260312-184330",  // hardened r1
			"20260312-201618",  // hardened+kb r1
			"20260313-172015",  // hardened+sae r1
			"20260312-211316",  // hardened+skills r1
			"20260312-215015",  // hardened+skills+sae r1
			"20260312-223105",  // hardened+skills+sae+forge r1
			"20260313-210027",  // hardened r2
			"20260313-212231",  // hardened+skills+sae r2
			"20260313-215310",  // hardened+kb r2
			"20260313-221701",  // hardened+sae r2
			"20260313-223731",  // simple r2
			"20260313-225818",  // hardened+skills r2
			"20260313-172615",  // hardened+skills+sae+forge r2
			"20260313-231850",  // hardened+skills+sae+forge r3 (partial — forge timeout)
			"20260313-235458",  // hardened r3
			"20260314-003525",  // hardened+skills+sae r3
			"20260314-010341",  // hardened+kb r3
			"20260314-013345",  // hardened+sae r3
			"20260314-031403"   // hardened+skills r3
	);

	public static void main(String[] args) {
		System.setProperty("java.net.preferIPv4Stack", "true");

		Path projectRoot = Path.of(System.getProperty("user.dir"));
		List<String> targetSessions = new ArrayList<>();
		Set<Integer> tiers = new TreeSet<>(Set.of(1, 2, 3));
		boolean regenerateJacoco = false;
		boolean dryRun = false;

		for (int i = 0; i < args.length; i++) {
			switch (args[i]) {
				case "--session" -> {
					if (i + 1 >= args.length) { logger.error("--session requires a name"); System.exit(1); }
					targetSessions.add(args[++i]);
				}
				case "--tiers" -> {
					if (i + 1 >= args.length) { logger.error("--tiers requires values"); System.exit(1); }
					tiers = Arrays.stream(args[++i].split(","))
							.map(String::trim).map(Integer::parseInt)
							.collect(Collectors.toCollection(TreeSet::new));
				}
				case "--regenerate-jacoco" -> regenerateJacoco = true;
				case "--dry-run" -> dryRun = true;
				case "--project-root" -> {
					if (i + 1 >= args.length) { logger.error("--project-root requires a path"); System.exit(1); }
					projectRoot = Path.of(args[++i]);
				}
				default -> { logger.error("Unknown argument: {}", args[i]); System.exit(1); }
			}
		}

		List<String> sessions = targetSessions.isEmpty() ? VALID_SESSIONS : targetSessions;
		Path sessionsDir = projectRoot.resolve("results/code-coverage-v2/sessions");
		Path judgePromptPath = projectRoot.resolve("plans/prompts/judge-practice-adherence.txt");
		ObjectMapper mapper = buildMapper();
		Jury jury = buildJury(judgePromptPath, tiers);

		logger.info("RejudgeApp: sessions={}, tiers={}, regenerateJacoco={}, dryRun={}",
				sessions.size(), tiers, regenerateJacoco, dryRun);

		int totalUpdated = 0;
		for (String sessionName : sessions) {
			totalUpdated += rejudgeSession(sessionsDir.resolve(sessionName), jury, tiers,
					regenerateJacoco, dryRun, mapper);
		}
		logger.info("Done. Total items updated: {}", totalUpdated);
	}

	private static int rejudgeSession(Path sessionDir, Jury jury, Set<Integer> tiers,
			boolean regenerateJacoco, boolean dryRun, ObjectMapper mapper) {
		if (!Files.isDirectory(sessionDir)) {
			logger.warn("Session directory not found: {}", sessionDir);
			return 0;
		}

		List<Path> variantFiles;
		try (var stream = Files.list(sessionDir)) {
			variantFiles = stream
					.filter(p -> p.toString().endsWith(".json")
							&& !p.getFileName().toString().startsWith("session"))
					.collect(Collectors.toList());
		}
		catch (IOException ex) {
			logger.error("Failed to list session directory: {}", sessionDir, ex);
			return 0;
		}

		int updated = 0;
		for (Path variantFile : variantFiles) {
			updated += rejudgeVariant(variantFile, jury, tiers, regenerateJacoco, dryRun, mapper);
		}
		return updated;
	}

	private static int rejudgeVariant(Path variantFile, Jury jury, Set<Integer> tiers,
			boolean regenerateJacoco, boolean dryRun, ObjectMapper mapper) {
		String variant = variantFile.getFileName().toString().replace(".json", "");
		logger.info("--- {} ---", variant);

		ObjectNode root;
		try {
			root = (ObjectNode) mapper.readTree(variantFile.toFile());
		}
		catch (IOException ex) {
			logger.error("Failed to read {}", variantFile, ex);
			return 0;
		}

		ArrayNode items = (ArrayNode) root.get("items");
		if (items == null || items.isEmpty()) {
			logger.info("  No items in {}", variantFile.getFileName());
			return 0;
		}

		int updated = 0;
		for (JsonNode itemNode : items) {
			String itemSlug = itemNode.path("itemSlug").asText("unknown");

			if (!itemNode.path("success").asBoolean(false)) {
				logger.info("  Skipping {} — agent invocation failed", itemSlug);
				continue;
			}

			JsonNode wpNode = itemNode.path("workspacePath");
			if (wpNode.isMissingNode() || wpNode.isNull()) {
				logger.warn("  Skipping {} — no workspacePath in JSON", itemSlug);
				continue;
			}
			Path workspace = Path.of(wpNode.asText());
			if (!Files.isDirectory(workspace)) {
				logger.warn("  Skipping {} — workspace not found: {}", itemSlug, workspace);
				continue;
			}

			// Regenerate jacoco.xml from existing jacoco.exec (needed for T1/T2)
			if (regenerateJacoco && (tiers.contains(1) || tiers.contains(2))) {
				regenerateJaCoCoReport(workspace);
			}

			// Extract metadata from invocationResult.metadata (String-typed key-value map)
			Map<String, Object> metadata = new HashMap<>();
			JsonNode invMeta = itemNode.path("invocationResult").path("metadata");
			if (!invMeta.isMissingNode() && invMeta.isObject()) {
				invMeta.fields().forEachRemaining(e -> metadata.put(e.getKey(), e.getValue().asText()));
			}

			JudgmentContext ctx = JudgmentContext.builder()
					.goal("Improve test coverage for " + itemSlug)
					.workspace(workspace)
					.executionTime(Duration.ofMillis(itemNode.path("durationMs").asLong(0)))
					.startedAt(Instant.now())
					.status(ExecutionStatus.SUCCESS)
					.metadata(metadata)
					.build();

			Verdict verdict;
			try {
				verdict = jury.vote(ctx);
			}
			catch (Exception ex) {
				logger.error("  Jury failed for {}: {}", itemSlug, ex.getMessage(), ex);
				continue;
			}

			boolean newPassed = VerdictExtractor.passed(verdict);
			Map<String, Double> newScores = VerdictExtractor.extractScores(verdict);

			if (dryRun) {
				logger.info("  [DRY-RUN] {} → passed={}, scores={}", itemSlug, newPassed, newScores);
				updated++;
				continue;
			}

			// Update item in-place: merge new scores (preserve existing T0 CommandJudge score)
			ObjectNode itemObj = (ObjectNode) itemNode;
			ObjectNode scoresNode = itemObj.has("scores")
					? (ObjectNode) itemObj.get("scores")
					: mapper.createObjectNode();
			newScores.forEach(scoresNode::put);
			itemObj.set("scores", scoresNode);
			itemObj.put("passed", newPassed);

			try {
				itemObj.set("verdict", mapper.valueToTree(verdict));
			}
			catch (Exception ex) {
				logger.warn("  Failed to serialize verdict for {}: {}", itemSlug, ex.getMessage());
			}

			logger.info("  {} → passed={}, scores={}", itemSlug, newPassed, newScores);
			updated++;
		}

		if (!dryRun && updated > 0) {
			recomputeAggregates(root, items, mapper);
			writeAtomic(variantFile, root, mapper);
		}
		return updated;
	}

	private static void recomputeAggregates(ObjectNode root, ArrayNode items, ObjectMapper mapper) {
		int passCount = 0;
		Map<String, Double> scoreSum = new HashMap<>();
		Map<String, Integer> scoreCnt = new HashMap<>();

		for (JsonNode item : items) {
			if (item.path("passed").asBoolean()) passCount++;
			JsonNode scoresNode = item.path("scores");
			if (!scoresNode.isMissingNode()) {
				scoresNode.fields().forEachRemaining(e -> {
					double v = e.getValue().asDouble();
					scoreSum.merge(e.getKey(), v, Double::sum);
					scoreCnt.merge(e.getKey(), 1, Integer::sum);
				});
			}
		}

		root.put("passRate", items.size() > 0 ? (double) passCount / items.size() : 0.0);

		ObjectNode aggScores = mapper.createObjectNode();
		scoreSum.forEach((k, sum) -> aggScores.put(k, sum / scoreCnt.get(k)));
		root.set("aggregateScores", aggScores);
	}

	private static void writeAtomic(Path targetFile, ObjectNode root, ObjectMapper mapper) {
		Path tmpFile = targetFile.resolveSibling(".rejudge-" + targetFile.getFileName());
		try {
			mapper.writeValue(tmpFile.toFile(), root);
			Files.move(tmpFile, targetFile, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
			logger.info("Wrote {}", targetFile.getFileName());
		}
		catch (IOException ex) {
			try { Files.deleteIfExists(tmpFile); } catch (IOException ignored) { }
			throw new UncheckedIOException("Failed to write " + targetFile, ex);
		}
	}

	private static void regenerateJaCoCoReport(Path workspace) {
		logger.info("  Regenerating jacoco.xml from jacoco.exec in {}", workspace.getFileName());
		MavenBuildRunner.BuildResult result = MavenBuildRunner.runBuild(
				workspace, 5, "jacoco:report",
				"-Dspring-javaformat.skip=true", "-Dcheckstyle.skip=true");
		if (!result.success()) {
			String snippet = result.output().substring(0, Math.min(300, result.output().length()));
			logger.warn("  jacoco:report failed: {}", snippet);
		}
	}

	// ---- Jury construction ----

	private static Jury buildJury(Path judgePromptPath, Set<Integer> tiers) {
		record TierDef(int num, org.springaicommunity.judge.Judge judge, TierPolicy defaultPolicy) {}

		List<TierDef> all = List.of(
				new TierDef(1, new CoveragePreservationJudge(), TierPolicy.REJECT_ON_ANY_FAIL),
				new TierDef(2, new CoverageImprovementJudge(50.0, 80.0), TierPolicy.ACCEPT_ON_ALL_PASS),
				new TierDef(3, new TestQualityJudge(
						TestQualityJudge.defaultAgentClientFactory("claude-sonnet-4-6", Duration.ofMinutes(3)),
						judgePromptPath), TierPolicy.FINAL_TIER)
		);

		List<TierDef> selected = all.stream()
				.filter(t -> tiers.contains(t.num()))
				.collect(Collectors.toList());

		if (selected.isEmpty()) {
			throw new IllegalArgumentException("No valid tiers selected from: " + tiers);
		}

		CascadedJury.Builder builder = CascadedJury.builder();
		for (int i = 0; i < selected.size(); i++) {
			TierDef td = selected.get(i);
			TierPolicy policy = (i == selected.size() - 1) ? TierPolicy.FINAL_TIER : td.defaultPolicy();
			Jury tierJury = SimpleJury.builder()
					.votingStrategy(new ConsensusStrategy())
					.judge(td.judge())
					.build();
			builder.tier("tier-" + td.num(), tierJury, policy);
		}
		return builder.build();
	}

	// ---- ObjectMapper for JSON serialization ----

	private static ObjectMapper buildMapper() {
		ObjectMapper mapper = new ObjectMapper();
		mapper.registerModule(new JavaTimeModule());
		mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
		mapper.enable(SerializationFeature.INDENT_OUTPUT);
		mapper.disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
		mapper.addMixIn(Score.class, ScoreMixin.class);
		SimpleModule module = new SimpleModule();
		module.addSerializer(Throwable.class, new ThrowableSerializer());
		mapper.registerModule(module);
		return mapper;
	}

	// Mirrors ResultObjectMapper.ScoreMixin — deduction by unique property presence.
	@JsonTypeInfo(use = JsonTypeInfo.Id.DEDUCTION, defaultImpl = BooleanScore.class)
	@JsonSubTypes({ @JsonSubTypes.Type(BooleanScore.class), @JsonSubTypes.Type(NumericalScore.class),
			@JsonSubTypes.Type(CategoricalScore.class) })
	interface ScoreMixin {
	}

	static final class ThrowableSerializer extends StdSerializer<Throwable> {

		ThrowableSerializer() {
			super(Throwable.class);
		}

		@Override
		public void serialize(Throwable value, JsonGenerator gen, SerializerProvider provider) throws IOException {
			gen.writeStartObject();
			gen.writeStringField("className", value.getClass().getName());
			gen.writeStringField("message", value.getMessage());
			gen.writeEndObject();
		}

	}

}
