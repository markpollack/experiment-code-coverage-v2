package ai.tuvium.coverage;

import java.util.List;
import java.util.Map;

import org.springframework.lang.Nullable;

/**
 * Specification for a single experiment variant.
 *
 * @param name variant identifier (e.g., "hardened+skills")
 * @param promptFile path to prompt file (explore prompt for two-phase)
 * @param actPromptFile path to act-phase prompt (null = single-phase)
 * @param knowledgeDir relative path to knowledge directory (null = no KB)
 * @param knowledgeFiles specific KB files to inject (empty = none)
 * @param judgeOverrides judge configuration overrides (currently unused)
 * @param model model override (null = use defaultModel from config)
 * @param skillsInstall true = install spring-testing-skills before invocation
 */
public record VariantSpec(
		String name,
		String promptFile,
		@Nullable String actPromptFile,
		@Nullable String knowledgeDir,
		List<String> knowledgeFiles,
		@Nullable Map<String, String> judgeOverrides,
		@Nullable String model,
		boolean skillsInstall) {

	public VariantSpec(String name, String promptFile, @Nullable String knowledgeDir,
			List<String> knowledgeFiles) {
		this(name, promptFile, null, knowledgeDir, knowledgeFiles, null, null, false);
	}

	/** Whether this variant uses a two-phase (explore + act) invocation. */
	public boolean isTwoPhase() {
		return actPromptFile != null;
	}

}
