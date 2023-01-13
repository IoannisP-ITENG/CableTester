#TODO should be part of faebryk

from typing import Any, Callable, Dict, List, Tuple
from typing_extensions import Self

from sexpdata import Symbol
from pathlib import Path

import sexpdata

class Node:
    def __init__(self, node) -> None:
        assert isinstance(node, list)
        self.node = node

    @classmethod
    def from_node(cls, node: "Node"):
        return cls(node.node)

    def get(self, key: List[Callable[[Any], bool]]) -> List["Node"]:
        result = [
            Node(search_node)
            for search_node in self.node
            if isinstance(search_node, list) and key[0](search_node)
        ]
        assert len(result) > 0, f"not found in {self}"

        if len(key) == 1:
            return result
        else:
            return [sub for next_node in result for sub in next_node.get(key[1:])]

    def get_prop(self, key: str) -> List["Node"]:
        return self.get([lambda n: n[0] == Symbol(key)])

    def append(self, node: "Node"):
        self.node.append(node.node)

    def __str__(self) -> str:
        return str(self.node)


class PCB(Node):
    @property
    def footprints(self) -> List["Footprint"]:
        return [Footprint.from_node(n) for n in self.get_prop("footprint")]

    @classmethod
    def load(cls, path: Path):
        return cls(sexpdata.loads(path.read_text()))

    def dump(self, path: Path):
        pcbsexpout = sexpdata.dumps(self.node)
        return path.write_text(pcbsexpout)


class Footprint(Node):
    @property
    def reference(self) -> "Text":
        return Text.from_node(
            self.get([lambda n: n[0:2] == [Symbol("fp_text"), Symbol("reference")]])[0]
        )

    @property
    def value(self) -> "Text":
        return Text.from_node(
            self.get([lambda n: n[0:2] == [Symbol("fp_text"), Symbol("value")]])[0]
        )

    @property
    def user_text(self) -> List["Text"]:
        return list(
            map(
                Text.from_node,
                self.get([lambda n: n[0:2] == [Symbol("fp_text"), Symbol("user")]]),
            )
        )

    @property
    def at(self):
        return At.from_node(self.get_prop("at")[0])

    @property
    def name(self) -> str:
        return self.node[1]


class Text(Node):
    Font = Tuple[float, float, float]

    @property
    def text_type(self) -> str:
        return self.node[1].value()

    @property
    def layer(self) -> Node:
        return self.get_prop("layer")[0]

    @layer.setter
    def layer(self, value: str):
        self.layer.node[1] = value

    @property
    def text(self) -> str:
        return self.node[2]

    @text.setter
    def text(self, value: str):
        self.node[2] = value

    @property
    def at(self):
        return At.from_node(self.get_prop("at")[0])

    @property
    def font(self) -> Font:
        font = self.get_prop("effects")[0].get_prop("font")[0]
        return (
            font.get_prop("size")[0].node[1:3] + font.get_prop("thickness")[0].node[1]
        )

    @font.setter
    def font(self, value: Font):
        font = self.get_prop("effects")[0].get_prop("font")[0]
        font.get_prop("size")[0].node[1:3] = value[0:2]
        font.get_prop("thickness")[0].node[1] = value[2]

    def __repr__(self) -> str:
        return f"Text[{self.node}]"

    @classmethod
    def factory(cls, text: str, at: "At", layer: str, font: Font, tstamp: str):
        #TODO make more generic
        return Text(
            [
                Symbol("fp_text"),
                Symbol("user"),
                text,
                at.node,
                [Symbol("layer"), layer],
                [Symbol("effects"), [Symbol("font"), [Symbol("size"), *font[0:2]], [Symbol("thickness"), font[2]]]],
                [Symbol("tstamp"), tstamp]
            ]
        )


class At(Node):
    Coord =  Tuple[float, float, float]

    @property
    def coord(self) -> Coord:
        if len(self.node[1:]) < 3:
            return tuple(self.node[1:] + [0])
        return tuple(self.node[1:4])

    @coord.setter
    def coord(self, value: Coord):
        self.node[1:4] = list(value)


    @classmethod
    def factory(cls, value: Coord):
        out = cls([Symbol("at")])
        out.coord = value
        return out