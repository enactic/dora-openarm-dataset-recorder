# dora-openarm-dataset-recorder

A [Dora](https://dora-rs.ai/) node that records data as an OpenArm dataset.

## Timestamps

For `arm_left_observation` and `arm_right_observation`, the recorded `timestamp`
uses `metadata.observation_timestamp` when present, falling back to
`metadata.timestamp` for older producers. Integer timestamps are Unix
nanoseconds. Actions, lifter observations, and camera images continue to use
`metadata.timestamp`.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

Copyright 2026 Enactic, Inc.

## Code of Conduct

All participation in the OpenArm project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
