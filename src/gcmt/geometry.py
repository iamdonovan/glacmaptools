import os
from pathlib import Path
import geopandas as gpd
import geoutils as gu
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
            overlap_gdf = self.get_overlaps(pairs)

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
