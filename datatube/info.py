from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import reprlib
from typing import Any, Iterable, Iterator

import validators

from datatube.error import error_trace


class PropertyDict:

    __slots__ = ("_immutable")

    def __init__(self, immutable: bool = False):
        if not isinstance(immutable, bool):
            err_msg = (f"[{error_trace()}] `immutable` must be a boolean "
                       f"(received object of type: {type(immutable)})")
            raise TypeError(err_msg)
        self._immutable = immutable

    @property
    def immutable(self) -> bool:
        return self._immutable

    def items(self) -> Iterator[tuple[str, Any]]:
        return zip(self.keys(), self.values())

    def keys(self) -> Iterator[str]:
        is_property = lambda a: isinstance(getattr(type(self), a), property)
        return (a for a in dir(type(self))
                if is_property(a) and a != "immutable")

    def values(self) -> Iterator[Any]:
        return (getattr(self, attr) for attr in self.keys())

    def __contains__(self, key: str) -> bool:
        return key in self.keys()

    def __eq__(self, other: dict | PropertyDict) -> bool:
        if not issubclass(type(other), (dict, PropertyDict)):
            err_msg = (f"[{error_trace()}] `other` must be another "
                       f"PropertyDict object or a base dictionary containing "
                       f"equivalent information (received object of type: "
                       f"{type(other)})")
            raise TypeError(err_msg)
        if len(self) != len(other):
            return False
        for key, val in self.items():
            if key not in other or val != other[key]:
                return False
        return True

    def __getitem__(self, key: str) -> Any:
        if not isinstance(key, str):
            err_msg = (f"[{error_trace()}] key must be a string (received "
                       f"object of type: {type(key)})")
            raise TypeError(err_msg)
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def __hash__(self) -> int:
        if not self.immutable:
            err_msg = (f"[{error_trace()}] PropertyDict cannot be hashed: "
                       f"instance must be immutable")
            raise TypeError(err_msg)  # hash(mutable) always throws TypeError
        return hash(tuple(self.items()))

    def __iter__(self) -> Iterable[str]:
        yield from self.keys()

    def __len__(self) -> int:
        # this will always evaluate to the number of @property attributes
        return len(list(self.keys()))

    def __repr__(self) -> str:
        return f"PropertyDict(immutable={self.immutable})"

    def __setitem__(self, key: str, val: Any) -> None:
        if not isinstance(key, str):
            err_msg = (f"[{error_trace()}] key must be a string (received "
                       f"object of type: {type(key)})")
            raise TypeError(err_msg)
        if key not in self.keys():
            raise KeyError(key)
        setattr(self, key, val)

    def __str__(self) -> str:
        str_repr = reprlib.Repr()
        contents = []
        for k, v in self.items():
            if issubclass(type(v), PropertyDict):
                contents.append(f"{repr(k)}: {str(v)}")
            elif isinstance(v, str):
                contents.append(f"{repr(k)}: {str_repr.repr(v)}")
            else:
                contents.append(f"{repr(k)}: {repr(v)}")
        return f"{{{', '.join(contents)}}}"


class ChannelInfo(PropertyDict):

    __slots__ = ("_channel_id", "_channel_name", "_html", "_last_updated")

    def __init__(self,
                 channel_id: str,
                 channel_name: str,
                 last_updated: datetime,
                 about_html: str,
                 community_html: str,
                 featured_channels_html: str,
                 videos_html: str,
                 immutable: bool = False):
        super().__init__(immutable=immutable)
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.last_updated = last_updated
        self.html = ChannelInfo.HtmlDict(
            about=about_html,
            community=community_html,
            featured_channels=featured_channels_html,
            videos=videos_html,
            immutable=immutable
        )

    @classmethod
    def from_json(cls, json_path: Path, immutable: bool = False) -> ChannelInfo:
        if not isinstance(json_path, Path):
            err_msg = (f"[{error_trace()}] `json_path` must be Path-like "
                       f"(received object of type: {type(json_path)})")
            raise TypeError(err_msg)
        if not json_path.exists():
            err_msg = (f"[{error_trace()}] `json_path` does not exist: "
                       f"{json_path}")
            raise ValueError(err_msg)
        if json_path.suffix != ".json":
            err_msg = (f"[{error_trace()}] `json_path` does not point to a "
                       f".json file: {json_path}")
            raise ValueError(err_msg)
        with json_path.open("r") as json_file:
            saved = json.load(json_file)
        return cls(channel_id=saved["channel_id"],
                   channel_name=saved["channel_name"],
                   last_updated=datetime.fromisoformat(saved["last_updated"]),
                   about_html=saved["html"]["about"],
                   community_html=saved["html"]["community"],
                   featured_channels_html=saved["html"]["featured_channels"],
                   videos_html=saved["html"]["videos"],
                   immutable=immutable)

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @channel_id.setter
    def channel_id(self, new_id: str) -> None:
        if self.immutable and hasattr(self, "_channel_id"):
            err_msg = (f"[{error_trace()}] cannot reassign `channel_id`: "
                       f"ChannelInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `channel_id` must be a 24-character "
                   f"ExternalId string starting with 'UC'")
        if not isinstance(new_id, str):
            context = f"(received object of type: {type(new_id)})"
            raise TypeError(f"{err_msg} {context}")
        if len(new_id) != 24 or not new_id.startswith("UC"):
            context = f"(received: {repr(new_id)})"
            raise ValueError(f"{err_msg} {context}")
        self._channel_id = new_id

    @property
    def channel_name(self) -> str:
        return self._channel_name

    @channel_name.setter
    def channel_name(self, new_name: str) -> None:
        if self.immutable and hasattr(self, "_channel_name"):
            err_msg = (f"[{error_trace()}] cannot reassign `channel_name`: "
                       f"ChannelInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `channel_name` must be a non-empty "
                   f"string")
        if not isinstance(new_name, str):
            context = f"(received object of type: {type(new_name)})"
            raise TypeError(f"{err_msg} {context}")
        if not new_name:
            context = f"(received: {repr(new_name)})"
            raise ValueError(f"{err_msg} {context}")
        self._channel_name = new_name

    @property
    def html(self) -> ChannelInfo.HtmlDict:
        return self._html

    @html.setter
    def html(self, new_html: ChannelInfo.HtmlDict | dict[str, str]) -> None:
        if self.immutable and hasattr(self, "_html"):
            err_msg = (f"[{error_trace()}] cannot reassign `html`: "
                       f"ChannelInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `html` must be a ChannelInfo.HtmlDict "
                   f"object or a base dictionary containing equivalent "
                   f"information")
        if not isinstance(new_html, (ChannelInfo.HtmlDict, dict)):
            context = f"(received object of type: {type(new_html)})"
            raise TypeError(f"{err_msg} {context}")
        if isinstance(new_html, dict):
            try:
                new_html = ChannelInfo.HtmlDict(**new_html)
            except (TypeError, ValueError) as err:
                context = (f"(could not convert base dictionary)")
                raise ValueError(f"{err_msg} {context}") from err
        new_html._immutable = self.immutable
        self._html = new_html

    @property
    def last_updated(self) -> datetime:
        return self._last_updated

    @last_updated.setter
    def last_updated(self, new_time: datetime) -> None:
        if self.immutable and hasattr(self, "_last_updated"):
            err_msg = (f"[{error_trace()}] cannot reassign `last_updated`: "
                       f"ChannelInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `last_updated` must be a timezone-aware "
                   f"datetime.datetime object stating the last time this "
                   f"channel's information was checked for updates")
        if not isinstance(new_time, datetime):
            context = f"(received object of type: {type(new_time)})"
            raise TypeError(f"{err_msg} {context}")
        if new_time.tzinfo is None:
            context = (f"(timestamp has no timezone information: "
                       f"{repr(new_time)})")
            raise ValueError(f"{err_msg} {context}")
        current_time = datetime.now(timezone.utc)
        if new_time > current_time:
            context = f"(timestamp in the future: {new_time} > {current_time})"
            raise ValueError(f"{err_msg} {context}")
        self._last_updated = new_time

    def to_json(self,
                save_to: Path | None = None) -> dict[str, str | dict[str, str]]:
        json_dict = {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "last_updated": self.last_updated.isoformat(),
            "html": {
                "about": self.html.about,
                "community": self.html.community,
                "featured_channels": self.html.featured_channels,
                "videos": self.html.videos
            }
        }
        if save_to is not None:
            if not isinstance(save_to, Path):
                err_msg = (f"[{error_trace()}] `save_to` must be Path-like "
                           f"(received object of type: {type(save_to)})")
                raise TypeError(err_msg)
            if save_to.suffix != ".json":
                err_msg = (f"[{error_trace()}] `save_to` must end with a "
                           f".json file extension (received: {save_to})")
                raise ValueError(err_msg)
            save_to.parent.mkdir(parents=True, exist_ok=True)
            with save_to.open("w") as json_file:
                json.dump(json_dict, json_file)
        return json_dict

    def __repr__(self) -> str:
        fields = {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "last_updated": self.last_updated,
            "about_html": self.html["about"],
            "community_html": self.html["community"],
            "featured_channels_html": self.html["featured_channels"],
            "videos_html": self.html["videos"],
            "immutable": self.immutable
        }
        str_repr = reprlib.Repr()
        contents = []
        for k, v in fields.items():
            if isinstance(v, str):
                contents.append(f"{k}={str_repr.repr(v)}")
            else:
                contents.append(f"{k}={repr(v)}")
        return f"ChannelInfo({', '.join(contents)})"

    class HtmlDict(PropertyDict):

        __slots__ = ("_about", "_community", "_featured_channels", "_videos")

        def __init__(self,
                     about: str,
                     community: str,
                     featured_channels: str,
                     videos: str,
                     immutable: bool = False):
            super().__init__(immutable=immutable)
            self.about = about
            self.community = community
            self.featured_channels = featured_channels
            self.videos = videos

        @property
        def about(self) -> str:
            return self._about

        @about.setter
        def about(self, new_html: str) -> None:
            if self.immutable and hasattr(self, "_about"):
                err_msg = (f"[{error_trace()}] cannot reassign `about`: "
                           f"HtmlDict instance is immutable")
                raise AttributeError(err_msg)
            err_msg = f"[{error_trace()}] `about` must be a string"
            if not isinstance(new_html, str):
                context = f"(received object of type: {type(new_html)})"
                raise TypeError(f"{err_msg} {context}")
            self._about = new_html

        @property
        def community(self) -> str:
            return self._community

        @community.setter
        def community(self, new_html: str) -> None:
            if self.immutable and hasattr(self, "_community"):
                err_msg = (f"[{error_trace()}] cannot reassign `community`: "
                           f"HtmlDict instance is immutable")
                raise AttributeError(err_msg)
            err_msg = f"[{error_trace()}] `community` must be a string"
            if not isinstance(new_html, str):
                context = f"(received object of type: {type(new_html)})"
                raise TypeError(f"{err_msg} {context}")
            self._community = new_html

        @property
        def featured_channels(self) -> str:
            return self._featured_channels

        @featured_channels.setter
        def featured_channels(self, new_html: str) -> None:
            if self.immutable and hasattr(self, "_featured_channels"):
                err_msg = (f"[{error_trace()}] cannot reassign "
                           f"`featured_channels`: HtmlDict instance is "
                           f"immutable")
                raise AttributeError(err_msg)
            err_msg = f"[{error_trace()}] `featured_channels` must be a string"
            if not isinstance(new_html, str):
                context = f"(received object of type: {type(new_html)})"
                raise TypeError(f"{err_msg} {context}")
            self._featured_channels = new_html

        @property
        def videos(self) -> str:
            return self._videos

        @videos.setter
        def videos(self, new_html: str) -> None:
            if self.immutable and hasattr(self, "_videos"):
                err_msg = (f"[{error_trace()}] cannot reassign `videos`: "
                           f"HtmlDict instance is immutable")
                raise AttributeError(err_msg)
            err_msg = f"[{error_trace()}] `videos` must be a string"
            if not isinstance(new_html, str):
                context = f"(received object of type: {type(new_html)})"
                raise TypeError(f"{err_msg} {context}")
            self._videos = new_html

        def __repr__(self) -> str:
            fields = {
                "about": self.about,
                "community": self.community,
                "featured_channels": self.featured_channels,
                "videos": self.videos,
                "immutable": self.immutable
            }
            str_repr = reprlib.Repr()
            contents = []
            for k, v in fields.items():
                if isinstance(v, str):
                    contents.append(f"{k}={str_repr.repr(v)}")
                else:
                    contents.append(f"{k}={repr(v)}")
            return f"ChannelInfo.HtmlDict({', '.join(contents)})"


class VideoInfo(PropertyDict):

    __slots__ = ("_channel_id", "_channel_name", "_video_id", "_video_title",
                 "_publish_date", "_last_updated", "_duration", "_description",
                 "_keywords", "_thumbnail_url")

    def __init__(self,
                 channel_id: str,
                 channel_name: str,
                 video_id: str,
                 video_title: str,
                 publish_date: datetime,
                 last_updated: datetime,
                 duration: timedelta,
                 description: str,
                 keywords: list[str] | tuple[str] | set[str],
                 thumbnail_url: str,
                 immutable: bool = False):
        super().__init__(immutable=immutable)
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.video_id = video_id
        self.video_title = video_title
        self.publish_date = publish_date
        self.last_updated = last_updated
        self.duration = duration
        self.description = description
        self.keywords = keywords
        self.thumbnail_url = thumbnail_url

    @classmethod
    def from_json(cls, json_path: Path, immutable: bool = False) -> VideoInfo:
        if not isinstance(json_path, Path):
            err_msg = (f"[{error_trace()}] `json_path` must be Path-like "
                       f"(received object of type: {type(json_path)})")
            raise TypeError(err_msg)
        if not json_path.exists():
            err_msg = (f"[{error_trace()}] `json_path` does not exist: "
                       f"{json_path}")
            raise ValueError(err_msg)
        if json_path.suffix != ".json":
            err_msg = (f"[{error_trace()}] `json_path` does not point to a "
                       f".json file: {json_path}")
            raise ValueError(err_msg)
        with json_path.open("r") as json_file:
            saved = json.load(json_file)
        return cls(channel_id=saved["channel_id"],
                   channel_name=saved["channel_name"],
                   video_id=saved["video_id"],
                   video_title=saved["video_title"],
                   publish_date=datetime.fromisoformat(saved["publish_date"]),
                   last_updated=datetime.fromisoformat(saved["last_updated"]),
                   duration=timedelta(seconds=saved["duration"]),
                   description=saved["description"],
                   keywords=saved["keywords"],
                   thumbnail_url=saved["thumbnail_url"],
                   immutable=immutable)

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @channel_id.setter
    def channel_id(self, new_id: str) -> None:
        if self.immutable and hasattr(self, "_channel_id"):
            err_msg = (f"[{error_trace()}] cannot reassign `channel_id`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `channel_id` must be a 24-character "
                   f"ExternalId string starting with 'UC'")
        if not isinstance(new_id, str):
            context = f"(received object of type: {type(new_id)})"
            raise TypeError(f"{err_msg} {context}")
        if len(new_id) != 24 or not new_id.startswith("UC"):
            context = f"(received: {repr(new_id)})"
            raise ValueError(f"{err_msg} {context}")
        self._channel_id = new_id

    @property
    def channel_name(self) -> str:
        return self._channel_name

    @channel_name.setter
    def channel_name(self, new_name: str) -> None:
        if self.immutable and hasattr(self, "_channel_name"):
            err_msg = (f"[{error_trace()}] cannot reassign `channel_name`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `channel_name` must be a non-empty "
                   f"string")
        if not isinstance(new_name, str):
            context = f"(received object of type: {type(new_name)})"
            raise TypeError(f"{err_msg} {context}")
        if not new_name:
            context = f"(received: {repr(new_name)})"
            raise ValueError(f"{err_msg} {context}")
        self._channel_name = new_name

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, new_description: str) -> None:
        if self.immutable and hasattr(self, "_description"):
            err_msg = (f"[{error_trace()}] cannot reassign `description`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = f"[{error_trace()}] `description` must be a string"
        if not isinstance(new_description, str):
            context = f"(received object of type: {type(new_description)})"
            raise TypeError(f"{err_msg} {context}")
        self._description = new_description

    @property
    def duration(self) -> timedelta:
        return self._duration

    @duration.setter
    def duration(self, new_duration: timedelta) -> None:
        if self.immutable and hasattr(self, "_duration"):
            err_msg = (f"[{error_trace()}] cannot reassign `duration`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `duration` must be a datetime.timedelta "
                   f"object describing the video's total runtime")
        if not isinstance(new_duration, timedelta):
            context = f"(received object of type: {type(new_duration)})"
            raise TypeError(f"{err_msg} {context}")
        if new_duration < timedelta():
            context = (f"(duration cannot be negative: {new_duration} < "
                       f"{timedelta()})")
            raise ValueError(f"{err_msg} {context}")
        self._duration = new_duration

    @property
    def keywords(self) -> list[str] | tuple[str]:
        return self._keywords

    @keywords.setter
    def keywords(self, new_keywords: list[str] | tuple[str] | set[str]) -> None:
        if self.immutable and hasattr(self, "_keywords"):
            err_msg = (f"[{error_trace()}] cannot reassign `keywords`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `keywords` must be a list, tuple, or "
                   f"set of keyword strings associated with this video")
        if not isinstance(new_keywords, (list, tuple, set)):
            context = f"(received object of type: {type(new_keywords)})"
            raise TypeError(f"{err_msg} {context}")
        for index, keyword in enumerate(new_keywords):
            if not isinstance(keyword, str):
                context = f"(received keyword of type: {type(keyword)})"
                raise TypeError(f"{err_msg} {context}")
            if not keyword:
                context = f"(received empty keyword at index: {index})"
                raise ValueError(f"{err_msg} {context}")
        if self.immutable:
            self._keywords = tuple(new_keywords)
        else:
            self._keywords = list(new_keywords)

    @property
    def last_updated(self) -> datetime:
        return self._last_updated

    @last_updated.setter
    def last_updated(self, new_date: datetime) -> None:
        if self.immutable and hasattr(self, "_last_updated"):
            err_msg = (f"[{error_trace()}] cannot reassign `last_updated`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `last_updated` must be a timezone-aware "
                   f"datetime.datetime object stating the last time this "
                   f"video's data was requested from YouTube")
        if not isinstance(new_date, datetime):
            context = f"(received object of type: {type(new_date)})"
            raise TypeError(f"{err_msg} {context}")
        if new_date.tzinfo is None:
            context = f"(datetime has no timezone: {repr(new_date)})"
            raise ValueError(f"{err_msg} {context}")
        current_time = datetime.now(timezone.utc)
        if new_date > current_time:
            context = (f"(datetime cannot be in the future: {new_date} > "
                       f"{current_time})")
            raise ValueError(f"{err_msg} {context}")
        if hasattr(self, "_publish_date") and new_date < self.publish_date:
            context = (f"(datetime cannot be less than `publish_date`: "
                       f"{new_date} < {self.publish_date})")
            raise ValueError(f"{err_msg} {context}")
        self._last_updated = new_date

    @property
    def publish_date(self) -> datetime:
        return self._publish_date

    @publish_date.setter
    def publish_date(self, new_date: datetime) -> None:
        if self.immutable and hasattr(self, "_publish_date"):
            err_msg = (f"[{error_trace()}] cannot reassign `publish_date`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `publish_date` must be a timezone-aware "
                   f"datetime.datetime object stating when this video was "
                   f"uploaded to youtube")
        if not isinstance(new_date, datetime):
            context = f"(received object of type: {type(new_date)})"
            raise TypeError(f"{err_msg} {context}")
        if new_date.tzinfo is None:
            context = f"(datetime has no timezone: {repr(new_date)})"
            raise ValueError(f"{err_msg} {context}")
        if hasattr(self, "_last_updated") and new_date > self.last_updated:
            context = (f"(datetime cannot be greater than `last_updated`: "
                       f"{new_date} > {self.last_updated})")
            raise ValueError(f"{err_msg} {context}")
        self._publish_date = new_date

    @property
    def thumbnail_url(self) -> str:
        return self._thumbnail_url

    @thumbnail_url.setter
    def thumbnail_url(self, new_url: str) -> None:
        if self.immutable and hasattr(self, "_thumbnail_url"):
            err_msg = (f"[{error_trace()}] cannot reassign `thumbnail_url`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `thumbnail_url` must be a valid url "
                   f"string")
        if not isinstance(new_url, str):
            context = f"(received object of type: {type(new_url)})"
            raise TypeError(f"{err_msg} {context}")
        if not validators.url(new_url):
            context = f"(not a valid url: {new_url})"
            raise ValueError(f"{err_msg} {context}")
        self._thumbnail_url = new_url

    @property
    def video_id(self) -> str:
        return self._video_id

    @video_id.setter
    def video_id(self, new_id: str) -> None:
        if self.immutable and hasattr(self, "_video_id"):
            err_msg = (f"[{error_trace()}] cannot reassign `video_id`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = (f"[{error_trace()}] `video_id` must be an 11-character "
                   f"video ID string")
        if not isinstance(new_id, str):
            context = f"(received object of type: {type(new_id)})"
            raise TypeError(f"{err_msg} {context}")
        if len(new_id) != 11:
            context = f"(received: {repr(new_id)})"
            raise ValueError(f"{err_msg} {context}")
        self._video_id = new_id

    @property
    def video_title(self) -> str:
        return self._video_title

    @video_title.setter
    def video_title(self, new_title: str) -> None:
        if self.immutable and hasattr(self, "_video_title"):
            err_msg = (f"[{error_trace()}] cannot reassign `video_title`: "
                       f"VideoInfo instance is immutable")
            raise AttributeError(err_msg)
        err_msg = f"[{error_trace()}] `video_title` must be a non-empty string"
        if not isinstance(new_title, str):
            context = f"(received object of type: {type(new_title)})"
            raise TypeError(f"{err_msg} {context}")
        if not new_title:
            context = f"(received: {repr(new_title)})"
            raise ValueError(f"{err_msg} {context}")
        self._video_title = new_title

    def to_json(self, save_to: Path | None = None) -> dict[str, str | int]:
        json_dict = {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "video_id": self.video_id,
            "video_title": self.video_title,
            "publish_date": self.publish_date.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "duration": self.duration.total_seconds(),
            "description": self.description,
            "keywords": list(self.keywords),
            "thumbnail_url": self.thumbnail_url
        }
        if save_to is not None:
            if not isinstance(save_to, Path):
                err_msg = (f"[{error_trace()}] `save_to` must be Path-like "
                           f"(received object of type: {type(save_to)})")
                raise TypeError(err_msg)
            if save_to.suffix != ".json":
                err_msg = (f"[{error_trace()}] `save_to` must end with a "
                           f".json file extension (received: {save_to})")
                raise ValueError(err_msg)
            save_to.parent.mkdir(parents=True, exist_ok=True)
            with save_to.open("w") as json_file:
                json.dump(json_dict, json_file)
        return json_dict

    def __repr__(self) -> str:
        fields = {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "video_id": self.video_id,
            "video_title": self.video_title,
            "publish_date": self.publish_date,
            "last_updated": self.last_updated,
            "duration": self.duration,
            "description": self.description,
            "keywords": self.keywords,
            "thumbnail_url": self.thumbnail_url,
            "immutable": self.immutable
        }
        str_repr = reprlib.Repr()
        contents = []
        for k, v in fields.items():
            if isinstance(v, str):
                contents.append(f"{k}={str_repr.repr(v)}")
            else:
                contents.append(f"{k}={repr(v)}")
        return f"VideoInfo({', '.join(contents)})"
