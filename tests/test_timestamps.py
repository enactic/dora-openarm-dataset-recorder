# Copyright 2026 Enactic, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import math
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import dora_openarm_dataset_recorder.main as recorder


class FakeNode:
    def __init__(self, events):
        self.events = events

    def __iter__(self):
        return iter(self.events)

    def dataflow_descriptor(self):
        return {"nodes": []}

    def node_config(self):
        return {"inputs": {}}


@pytest.fixture
def record_event(monkeypatch, tmp_path):
    monkeypatch.delenv("METADATA_FILE", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "recorder",
            "--directory",
            str(tmp_path),
            "--name",
            "dataset",
            "--operation-type",
            "teleop",
        ],
    )

    def record(event_id, value, metadata):
        events = [
            {
                "type": "INPUT",
                "id": "command",
                "value": pa.array(["start"]),
                "metadata": {},
            },
            {"type": "INPUT", "id": event_id, "value": value, "metadata": metadata},
            {
                "type": "INPUT",
                "id": "command",
                "value": pa.array(["success"]),
                "metadata": {},
            },
        ]
        monkeypatch.setattr(recorder.dora, "Node", lambda: FakeNode(events))
        recorder.main()
        return tmp_path / "dataset" / "episodes" / "0"

    return record


MESSAGE_NS = 1_700_000_000_123_456_789
OBSERVATION_NS = MESSAGE_NS - 5_000_000
MESSAGE_DATETIME = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            {"timestamp": MESSAGE_NS, "observation_timestamp": OBSERVATION_NS},
            OBSERVATION_NS,
        ),
        ({"timestamp": MESSAGE_NS, "observation_timestamp": 0}, 0),
        ({"timestamp": MESSAGE_NS}, MESSAGE_NS),
        (
            {"timestamp": MESSAGE_DATETIME},
            math.ceil(MESSAGE_DATETIME.timestamp() * 1_000_000_000),
        ),
        (
            {"timestamp": MESSAGE_NS, "observation_timestamp": MESSAGE_DATETIME},
            math.ceil(MESSAGE_DATETIME.timestamp() * 1_000_000_000),
        ),
    ],
)
def test_arm_observation_timestamp(record_event, side, structured, metadata, expected):
    value = (
        pa.array([{"qpos": [0.25, 0.5]}])
        if structured
        else pa.array([0.25, 0.5], type=pa.float32())
    )
    episode = record_event(f"arm_{side}_observation", value, metadata)

    table = pq.read_table(episode / "obs" / "arms" / side / "state.parquet")
    assert table["timestamp"].cast(pa.int64()).to_pylist() == [expected]
    assert table["qpos"].to_pylist() == [[0.25, 0.5]]


@pytest.mark.parametrize(
    ("event_id", "path"),
    [
        ("arm_left_action", "action/arms/left/state.parquet"),
        ("arm_right_action", "action/arms/right/state.parquet"),
        ("elevation_action", "action/lifter/elevation.parquet"),
        ("elevation_observation", "obs/lifter/elevation.parquet"),
    ],
)
def test_other_state_inputs_keep_message_timestamp(record_event, event_id, path):
    episode = record_event(
        event_id,
        pa.array([0.25], type=pa.float32()),
        {"timestamp": MESSAGE_NS, "observation_timestamp": OBSERVATION_NS},
    )
    table = pq.read_table(episode / path)
    assert table["timestamp"].cast(pa.int64()).to_pylist() == [MESSAGE_NS]


def test_camera_keeps_message_timestamp(record_event):
    episode = record_event(
        "camera_head",
        pa.array([1, 2], type=pa.uint8()),
        {
            "timestamp": MESSAGE_NS,
            "observation_timestamp": OBSERVATION_NS,
            "encoding": "jpg",
        },
    )
    directory = episode / "cameras" / "head"
    assert [path.name for path in directory.iterdir()] == [f"{MESSAGE_NS}.jpg"]
    assert (directory / f"{MESSAGE_NS}.jpg").read_bytes() == bytes([1, 2])
