# dora-openarm-dataset-recorder

A [Dora](https://dora-rs.ai/) node that records data as an OpenArm dataset.

## Timestamps

The first `arm_left_observation` or `arm_right_observation` selects the timestamp
field for both arms for the recorder process lifetime, including before recording
starts. It selects `metadata.observation_timestamp` when present, otherwise
`metadata.timestamp` for older producers, and logs the choice once.

The selection persists across episode completion, cancellation, and subsequent
starts. Later messages must contain the selected field; a missing field raises
an error. If `timestamp` was selected, later `observation_timestamp` fields are
ignored. Restart the recorder to select a different field.

Integer timestamps are Unix nanoseconds. Actions, lifter observations, and camera
images continue to use `metadata.timestamp` independently of the arm selection.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

Copyright 2026 Enactic, Inc.

## Code of Conduct

All participation in the OpenArm project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
