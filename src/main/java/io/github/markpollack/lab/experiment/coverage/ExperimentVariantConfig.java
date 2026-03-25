package io.github.markpollack.lab.experiment.coverage;

import java.util.List;

import io.github.markpollack.experiment.dataset.DatasetManager;
import org.springframework.lang.Nullable;

/**
 * Top-level experiment configuration loaded from experiment-config.yaml.
 */
public record ExperimentVariantConfig(
		String experimentName,
		String defaultModel,
		int timeoutMinutes,
		List<VariantSpec> variants,
		DatasetManager datasetManager,
		@Nullable String itemSlugFilter) {

	public ExperimentVariantConfig(String experimentName, String defaultModel, int timeoutMinutes,
			List<VariantSpec> variants, DatasetManager datasetManager) {
		this(experimentName, defaultModel, timeoutMinutes, variants, datasetManager, null);
	}

	public ExperimentVariantConfig withItemFilter(String itemSlug) {
		return new ExperimentVariantConfig(experimentName, defaultModel, timeoutMinutes,
				variants, datasetManager, itemSlug);
	}

}
