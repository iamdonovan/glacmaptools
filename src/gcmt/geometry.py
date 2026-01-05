import os
from pathlib import Path
import pandas as pd
import geopandas as gpd
import geoutils as gu
from . import utils
from typing import TypeVar, Union


# This is a generic Vector-type (if subclasses are made, this will change appropriately)
GlacierOutlinesType = TypeVar("GlacierOutlinesType", bound="GlacierOutlines")

class GlacierOutlines(gu.Vector):
    """

    A vector geometry representing glacier outlines, based on geoutils.Vector.

    Main attributes:
       ds: :class:`geopandas.GeoDataFrame`
           GeoDataFrame of the glacier outlines.
       crs: :class:`pyproject.crs.CRS`
           Coordinate reference system of the outlines.
       bounds: :class:`rio.coords.BoundingBox`
           Coordinate bounds of the outlines.

    Methods added beyond attributes/methods inherited from geoutils.Vector:

       validate(): check whether the outlines have topological or other errors.
       get_overlaps(): return a Vector object with all areas where outlines overlap.
       join_rgi(): join the outlines to RGI outlines
    """
    def __init__(self, *args, **kwargs):
        gu.Vector.__init__(self, *args, **kwargs)

    def validate(self,
                 overlap_ok: bool = False,
                 multi_ok: bool = False) -> None:
        """
        Checks the GlacierOutlines geometries for the following errors:

        - overlapping geometries. If overlaps are allowed, use overlap_ok=True.
        - multi-part geometries. If multi-part geometries are allowed, use multi_ok=True.
        - invalid geometries (using self.is_valid)

        By default, fails if any of the above checks fail. Once checks are passed, runs .remove_repeated_points() to
        remove any repeated nodes (with a tolerance of 1e-6), then saves to the cleaned/ directory.

        All errors (overlaps, multi-part geometries, invalid geometries) are saved to the errors/ directory for review.

        :param overlap_ok: outlines are allowed to overlap.
        :param multi_ok: outlines are allowed to be multi-part.
        """
        # run remove_repeated_points
        # check for invalid geometries using is_valid
        # - if invalid, give reason
        # output a file with "errors" that indicate which geometries are the problem
        output_prefix = os.path.splitext(os.path.basename(self.name))[0]

        has_overlap = False
        has_invalid = False

        # check for overlaps
        pairs = self._overlapping_inds()

        if len(pairs) > 0:
            overlap_gdf = self.get_overlaps()

            print(f"Found {len(pairs)} pairs of overlapping geometries.")
            print(f"Saving overlaps to errors/{output_prefix}_overlaps.gpkg for review.")
            os.makedirs('errors', exist_ok=True)

            overlap_gdf.to_file(Path('errors', output_prefix + '_overlaps.gpkg'))

            if not overlap_ok:
                has_overlap = True

        # check validity
        if not all(self.is_valid):
            os.makedirs('errors', exist_ok=True)
            has_invalid = True

            print('Invalid geometries found.')
            print(f"Saving invalid outlines to errors/{output_prefix}_invalid.gpkg for review.")
            invalid = self.ds.loc[~self.is_valid]
            invalid['reason'] = invalid.is_valid_reason()
            invalid.to_file(Path('errors', output_prefix + '_invalid.gpkg'))

        if not multi_ok:
            has_multi = not len(self.ds) == len(self.ds.explode())
            if has_multi:
                print('MultiPolygon geometries found.')
                print(f"Saving to errors/{output_prefix}_multi.gpkg for review.")

                exploded = self.explode()
                multiinds = exploded[exploded.ds.index.duplicated()].index.to_list()
                self[self.ds.index.isin(multiinds)].to_file(Path('errors', output_prefix + '_multi.gpkg'))
        else:
            has_multi = False

        # remove repeated points
        cleaned_geom = self.ds.remove_repeated_points(tolerance=1e-6)
        self['geometry'] = cleaned_geom

        assert not any([has_overlap, has_invalid, has_multi]), "One or more checks failed."

        print('All checks passed.')

        print(f"Saving outlines to cleaned/{output_prefix}.gpkg")
        os.makedirs('cleaned', exist_ok=True)
        self.to_file(Path('cleaned', output_prefix + '.gpkg'))

    def get_overlaps(self) -> gu.Vector:
        """
        Find all overlapping geometries in the current set of outlines.

        :return: the overlapping geometries.
        """
        pairs = self._overlapping_inds()

        geoms = []
        for ind1, ind2 in pairs:
            geoms.append(self.ds.loc[ind1, 'geometry'].intersection(self.ds.loc[ind2, 'geometry']))

        left, right = zip(*pairs)
        overlap_gdf = gu.Vector(gpd.GeoDataFrame(data={'geometry': geoms, 'ind1': left, 'ind2': right},
                                                       crs=self.crs)).explode()

        return overlap_gdf.explode()

    def _overlapping_inds(self) -> list[tuple[int, int]]:
        overlaps = []
        overlap_inds = []

        for n, ind in enumerate(self.index[:-1], 1):
            poly = self.ds.loc[ind, 'geometry']
            has_overlap = [g.overlaps(poly) for g in self.ds.loc[n + 1:, 'geometry']]

            if any(has_overlap):
                overlaps.append(ind)
                for oind, row in self.ds.loc[n + 1:].iterrows():
                    if row['geometry'].overlaps(poly):
                        overlap_inds.append((ind, oind))

        return overlap_inds

    def compute_difference(self, other: Union[GlacierOutlinesType, str, Path]) -> GlacierOutlinesType:
        """
        Compute the symmetric difference between the glacier outlines and another geometry, using the .union_all() of
        each set of outlines. Output is a Vector with a single attribute, 'difference', with the following values:

            - 'added': areas that are included in self but not in "other"
            - 'removed': areas that are included in "other" but not in self

        :param fn_update: the filename for the update vector file
        :param other: the other outlines, or the filename for the other vector file
        :return: the differenced geometries
        """
        if isinstance(other, (str, Path)):
            other = gu.Vector(other).union_all()
        else:
            other = other.union_all()

        update = self.union_all()

        removed = other.difference(update).explode()
        added = update.difference(other).explode()

        removed['difference'] = 'removed'
        added['difference'] = 'added'

        return gu.Vector(pd.concat([added.ds, removed.ds], ignore_index=True))

    def join_rgi(self,
                 rgi_reg: Union[int, str, Path],
                 rgi_dir: Union[str, Path] = 'rgi',
                 version: str = 'v7.0',
                 inplace: bool = False) -> Union[None, GlacierOutlinesType]:
        """
        Join the GlacierOutlines to overlapping RGI outlines. RGI outlines are first sub-sampled by intersecting with
        the total boundary of the GlacierOutlines geometries. The sub-sampled RGI outlines are then converted to a
        "representative point" before applying a spatial join to the GlacierOutlines geometries.

        :param rgi_dir: The path to the directory where the RGI files or folders are stored.
        :param rgi_reg: The RGI region name (e.g., RGI2000-v7.0-G-01_alaska) or number (e.g., 1 for region 01)
        :param version: The RGI version (v7.0 or v6.0)
        :param inplace: Whether to do the spatial join in-place, or create a new GlacierOutlines object.
        :return:
        """
        rgi_outlines = gu.Vector(utils.rgi_loader(rgi_dir, rgi_reg=rgi_reg, version=version))
        envelope = self.union_all().envelope.ds.loc[0, 'geometry']

        reduced = rgi_outlines[rgi_outlines.ds.to_crs(self.crs).intersects(envelope)].copy().ds
        reduced['geometry'] = reduced.to_crs(self.estimate_utm_crs()).representative_point().to_crs(self.crs)

        rgi_centers = gu.Vector(reduced)

        if inplace:
            self.ds = self.sjoin(rgi_centers).ds
            return None
        else:
            return self.sjoin(rgi_centers)

    def reindex(self, prefix: Union[None, str] = None) -> None:
        """
        Re-index the GlacierOutlines.

        :param prefix: a prefix to add to the index (e.g., "RGI60-01" or "LIA-01"). If not provided, defaults to the
           row number of the GeoDataFrame.
        """
        if prefix is None:
            self.ds.index = range(len(self.ds))
        else:
            ndigits = len(str(len(self.ds)))
            self.ds.index = [f"{prefix}.{str(n+1).zfill(ndigits)}" for n in range(len(self.ds))]
