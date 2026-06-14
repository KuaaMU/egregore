"""Tests for Topic models and store."""

import pytest
from pathlib import Path
import tempfile

from egregore.topic.models import Topic
from egregore.topic.store import TopicStore


def test_topic_creation():
    topic = Topic(title="Test", providers=["chatgpt", "grok"])
    assert topic.title == "Test"
    assert topic.providers == ["chatgpt", "grok"]
    assert topic.id  # auto-generated


def test_topic_set_url():
    topic = Topic(title="Test")
    topic.set_url("chatgpt", "https://chatgpt.com/c/xxx")
    assert topic.get_url("chatgpt") == "https://chatgpt.com/c/xxx"
    assert "chatgpt" in topic.providers


def test_topic_touch():
    topic = Topic(title="Test")
    old = topic.last_accessed
    topic.touch()
    assert topic.last_accessed >= old


def test_store_save_and_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TopicStore(Path(tmpdir) / "test.db")
        topic = Topic(title="Test Topic", providers=["chatgpt"])
        topic.set_url("chatgpt", "https://chatgpt.com/c/xxx")

        store.save(topic)
        loaded = store.get(topic.id)

        assert loaded is not None
        assert loaded.title == "Test Topic"
        assert loaded.providers == ["chatgpt"]
        assert loaded.get_url("chatgpt") == "https://chatgpt.com/c/xxx"

        store.close()


def test_store_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TopicStore(Path(tmpdir) / "test.db")
        store.save(Topic(title="A"))
        store.save(Topic(title="B"))
        store.save(Topic(title="C"))

        topics = store.list_all()
        assert len(topics) == 3

        store.close()


def test_store_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TopicStore(Path(tmpdir) / "test.db")
        topic = Topic(title="ToDelete")
        store.save(topic)
        assert store.get(topic.id) is not None

        store.delete(topic.id)
        assert store.get(topic.id) is None

        store.close()


def test_store_pinned_order():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TopicStore(Path(tmpdir) / "test.db")
        store.save(Topic(title="Normal"))
        store.save(Topic(title="Pinned", pinned=True))

        topics = store.list_all()
        assert topics[0].title == "Pinned"

        store.close()
