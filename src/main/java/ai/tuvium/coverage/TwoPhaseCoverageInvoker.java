package ai.tuvium.coverage;

import java.nio.file.Path;
import java.util.List;

import ai.tuvium.experiment.agent.InvocationContext;
import io.github.markpollack.journal.claude.PhaseCapture;
import io.github.markpollack.journal.claude.SessionLogParser;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.lang.Nullable;
import org.springaicommunity.claude.agent.sdk.ClaudeClient;
import org.springaicommunity.claude.agent.sdk.ClaudeSyncClient;
import org.springaicommunity.claude.agent.sdk.config.PermissionMode;
import org.springaicommunity.judge.coverage.JaCoCoReportParser.CoverageMetrics;

/**
 * Two-phase agent invoker — explore then act, within a single Claude session.
 * Used for variant 6 (hardened+skills+sae+forge).
 */
public class TwoPhaseCoverageInvoker extends AbstractCoverageAgentInvoker {

	private static final Logger logger = LoggerFactory.getLogger(TwoPhaseCoverageInvoker.class);

	private final String actPromptTemplate;

	public TwoPhaseCoverageInvoker(
			@Nullable Path knowledgeSourceDir,
			@Nullable List<String> knowledgeFiles,
			boolean skillsInstall,
			String actPromptTemplate) {
		super(knowledgeSourceDir, knowledgeFiles, skillsInstall);
		this.actPromptTemplate = actPromptTemplate;
	}

	@Override
	protected AgentResult invokeAgent(InvocationContext context, CoverageMetrics baseline) throws Exception {
		Path workspace = context.workspacePath();
		String model = context.model();

		String explorePrompt = buildPrompt(context.prompt(), baseline);
		String actPrompt = buildPrompt(actPromptTemplate, baseline);

		logger.info("Step 6: Two-phase invocation (model={})", model);

		try (ClaudeSyncClient client = ClaudeClient.sync()
				.workingDirectory(workspace)
				.model(model)
				.permissionMode(PermissionMode.DANGEROUSLY_SKIP_PERMISSIONS)
				.build()) {

			logger.info("Phase 1: Explore");
			client.connect(explorePrompt);
			PhaseCapture explore = SessionLogParser.parse(
					client.receiveResponse(), "explore", explorePrompt);
			logger.info("Explore: {} turns, {} in + {} out tokens, ${}",
					explore.numTurns(), explore.inputTokens(), explore.outputTokens(),
					String.format("%.4f", explore.totalCostUsd()));

			logger.info("Phase 2: Act");
			client.query(actPrompt);
			PhaseCapture act = SessionLogParser.parse(
					client.receiveResponse(), "act", actPrompt);
			logger.info("Act: {} turns, {} in + {} out tokens, ${}",
					act.numTurns(), act.inputTokens(), act.outputTokens(),
					String.format("%.4f", act.totalCostUsd()));

			String sessionId = act.sessionId() != null ? act.sessionId() : explore.sessionId();
			return new AgentResult(List.of(explore, act), sessionId);
		}
	}

}
