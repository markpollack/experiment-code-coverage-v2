package ai.tuvium.coverage.dataset;

import java.nio.file.Path;
import java.util.List;

import ai.tuvium.experiment.dataset.Dataset;
import ai.tuvium.experiment.dataset.DatasetItem;
import ai.tuvium.experiment.dataset.DatasetManager;
import ai.tuvium.experiment.dataset.DatasetVersion;
import ai.tuvium.experiment.dataset.ItemFilter;
import ai.tuvium.experiment.dataset.ResolvedItem;

/**
 * Wraps a {@link DatasetManager} to filter items by slug. Used for single-item
 * smoke testing via {@code --item <slug>}.
 */
public class SlugFilteringDatasetManager implements DatasetManager {

	private final DatasetManager delegate;

	private final String slug;

	public SlugFilteringDatasetManager(DatasetManager delegate, String slug) {
		this.delegate = delegate;
		this.slug = slug;
	}

	@Override
	public Dataset load(Path datasetDir) {
		return delegate.load(datasetDir);
	}

	@Override
	public List<DatasetItem> activeItems(Dataset dataset) {
		return delegate.activeItems(dataset).stream()
			.filter(item -> slug.equals(item.slug()))
			.toList();
	}

	@Override
	public List<DatasetItem> filteredItems(Dataset dataset, ItemFilter filter) {
		return delegate.filteredItems(dataset, filter).stream()
			.filter(item -> slug.equals(item.slug()))
			.toList();
	}

	@Override
	public DatasetVersion currentVersion(Dataset dataset) {
		return delegate.currentVersion(dataset);
	}

	@Override
	public ResolvedItem resolve(DatasetItem item) {
		return delegate.resolve(item);
	}

}
