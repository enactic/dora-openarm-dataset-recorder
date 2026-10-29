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

import sys
import threading

import pyarrow as pa
import pytest
import yaml

import dora_openarm_dataset_recorder.main as recorder


class FakeNode:
    def __init__(self, events):
        self.events = events
        self.read = 0

    def __iter__(self):
        for event in self.events:
            self.read += 1
            yield event

    def dataflow_descriptor(self):
        return {"nodes": []}

    def node_config(self):
        return {"inputs": {}}


def command(name, **metadata):
    return {
        "type": "INPUT",
        "id": "command",
        "value": pa.array([name]),
        "metadata": metadata,
    }


@pytest.fixture
def run_node(monkeypatch, tmp_path):
    monkeypatch.delenv("METADATA_FILE", raising=False)

    def run(node):
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
        monkeypatch.setattr(recorder.dora, "Node", lambda: node)
        recorder.main()
        with open(tmp_path / "dataset" / "metadata.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f)["episodes"]

    return run


@pytest.mark.parametrize("name", ["success", "fail", "cancel"])
def test_end_without_episode_is_ignored(run_node, name):
    episodes = run_node(
        FakeNode(
            [
                command(name),
                command("start", episode_number=1),
                command("success"),
            ]
        )
    )
    assert episodes == [{"id": "1", "success": True, "task_index": 0}]


def test_events_are_read_while_episode_is_written(run_node, monkeypatch):
    node = FakeNode(
        [
            command("start", episode_number=1),
            command("success"),
            command("start", episode_number=2),
            command("fail"),
        ]
    )
    all_read = threading.Event()
    finish = recorder.EpisodeWriter.finish

    def slow_finish(self):
        # The first finish() waits until every event has been read, which
        # only happens if events are read while the episode is written.
        if self._episode.number == 1:
            for _ in range(100):
                if node.read == len(node.events):
                    all_read.set()
                    break
                threading.Event().wait(0.01)
        finish(self)

    monkeypatch.setattr(recorder.EpisodeWriter, "finish", slow_finish)
    episodes = run_node(node)
    assert all_read.is_set()
    assert episodes == [
        {"id": "1", "success": True, "task_index": 0},
        {"id": "2", "success": False, "task_index": 0},
    ]


def test_event_reader_raises_node_error():
    class BrokenNode:
        def __iter__(self):
            yield command("start")
            raise RuntimeError("broken")

    reader = recorder.EventReader(BrokenNode())
    events = iter(reader)
    assert next(events)["value"].to_pylist() == ["start"]
    with pytest.raises(RuntimeError, match="broken"):
        next(events)
