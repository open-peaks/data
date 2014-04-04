# Open Peaks
An open source initiative focused on the geographic data of mountains. See the [index of all the mountains](https://github.com/open-peaks/data/blob/master/index.geojson) (updated daily).

## GeoJSON

All peak data is stored in geo-json. For more information visit: [http://geojson.org/](http://geojson.org/).

## Finding a Mountain/Peak

The directory structure for finding peaks is:

:continent/:country?/:state?/:name.geojson

## Contributing

Simply edit/add the mountains [geojson](http://geojson.org/) file in the proper directory and submit a pull request. Acceptable fields include:



| field | description | required/options
|:--|:--|:--
| type | use "Feature" |
| geometry.coordinates | [longitude, latitude] of the mountain | required
| geometry.type | use "Point" | required
| properties.name | name of the mountain | required
| properties.latitude | latitude of the mountain | required
| properties.longitude | longitude of the mountain | required
| properties.feet | height of the mountain in feet | required
| properties.meters | height of the mountain in meters | required
| properties.continent | continent of mountain | required
| properties.countries | countries mountain is in | required
| properties.regions | regions/ranges mountain is in | required
| properties.marker-symbol | use "triangle" | required
| properties.marker-size | see [sizes](#sizes) | required
| properties.state | state of mountain | optional

## Sizes

Use the following for marker sizes:

| height | size |
|:--|:--
| small | < 600m |
| medium | < 4200m |
| large | > 4200 |


## Questions / Complaints ?

Open a Github issue or email me at [jason@waldrip.net](mailto:jason@waldrip.net).
