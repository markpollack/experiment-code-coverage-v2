package io.github.markpollack.lab.experiment.coverage;

import java.nio.file.Path;
import java.util.List;

import io.github.markpollack.experiment.agent.InvocationContext;
import io.github.markpollack.journal.claude.PhaseCapture;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.lang.Nullable;
import org.springaicommunity.agents.client.AgentClient;
import org.springaicommunity.agents.client.AgentClientResponse;
import org.springaicommunity.agents.claude.ClaudeAgentModel;
import org.springaicommunity.agents.claude.ClaudeAgentOptions;
import org.springaicommunity.agents.model.AgentModel;
import org.springaicommunity.judge.coverage.JaCoCoReportParser.CoverageMetrics;

/**
 * Single-phase agent invoker — one AgentClient call per dataset item.
 * Used for variants 1–5 (simple, hardened, +kb, +skills, +skills+preanalysis).
 */
public class SinglePhaseCoverageInvoker extends AbstractCoverageAgentInvoker {

	private static final Logger logger = LoggerFactory.getLogger(SinglePhaseCoverageInvoker.class);

	public SinglePhaseCoverageInvoker(
			@Nullable Path knowledgeSourceDir,
			@Nullable List<String> knowledgeFiles,
			boolean skillsInstall) {
		super(knowledgeSourceDir, knowledgeFiles, skillsInstall);
	}

	@Override
	protected AgentResult invokeAgent(InvocationContext context, CoverageMetrics baseline) {
		Path workspace = context.workspacePath();
		logger.info("Step 6: Invoking agent (model={})", context.model());

		AgentModel agentModel = ClaudeAgentModel.builder()
				.workingDirectory(workspace)
				.defaultOptions(ClaudeAgentOptions.builder()
						.model(context.model())
						.yolo(true)
						.build())
				.build();

		AgentClient client = AgentClient.create(agentModel);
		String prompt = buildPrompt(context.prompt(), baseline);

		AgentClientResponse response = client.goal(prompt).workingDirectory(workspace).run();

		PhaseCapture capture = response.getPhaseCapture();
		if (capture != null) {
			logger.info("Agent exhaust: {} turns, {} in + {} out tokens, ${}",
					capture.numTurns(), capture.inputTokens(), capture.outputTokens(),
					String.format("%.4f", capture.totalCostUsd()));
		}

		List<PhaseCapture> phases = capture != null ? List.of(capture) : List.of();
		String sessionId = capture != null ? capture.sessionId() : null;
		return new AgentResult(phases, sessionId);
	}

}
