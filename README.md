# Cubing Contests Database Export Readme

- Export format version: v1
- Website: https://cubingcontests.com

This is a database export for Cubing Contests. When opening one of the CSV files, make sure to set , (comma) as the separator and " (double quote) as the string delimiter.

## License

The results in these exports are available under the [CC Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/) license.

## Using the export files

The CSV files can be used directly for putting together various statistics based on the data. They can also be imported using Supabase (e.g. for testing the website using real data in local development). The process for that is outlined in the [RecordRanks repository](https://codeberg.org/mintydev/RecordRanks) README.

Note that, due to limitations with the CSV format, empty string values are represented as `__EMPTY_STRING__` (e.g. in the `contests.description` column). You can (and should) safely change those values to empty strings.

## Attempt results

The results are stored in a format based on the WCA format. See the [WCA exports page](https://www.worldcubeassociation.org/export/results) for the details. The differences are outlined below.

Results for events of the "time" type use the max time value (8640000) for unknown time. This is used for Extreme BLD results, where the mere evidence of a successful attempt is an achievement in and of itself. This can only be set by an admin.

Results for events of the "multi" type are based on the WCA multi format. The difference is that these exports omit the leading 0/1 character (all results are based on the new format), allow multi results up to 9999 cubes instead of 99, time is stored as centiseconds instead of seconds, and DNFs are stored with all of the same information (e.g. "DNF (5/12 52:13)"), just as negative numbers. So the full format using WCA notation is as follows:

```
(-)DDDDTTTTTTTMMMM

isDnf              = the result is a negative value (all DNFs are treated as tied)
difference         = 9999 - |DDDD| (the latter is the absolute value of solved - missed, to accommodate DNFs)
timeInCentiseconds = TTTTTTT (8640000 means unknown time and is the maximum time value)
missed             = MMMM
solved             = difference + missed
attempted          = solved + missed
```
