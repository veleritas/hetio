# daniel.himmelstein@gmail.com
import abc
import itertools
import collections
import re

import hetio.abbreviation

direction_to_inverse = {'forward': 'backward',
                         'backward': 'forward',
                         'both': 'both'}

direction_to_abbrev = {'forward': '>', 'backward': '<', 'both': '-'}
direction_to_unicode_abbrev = {'forward': '→', 'backward': '←', 'both': '–'}

class ElemMask(object):

    def __init__(self):
        self.masked = False

    def is_masked(self):
        return self.masked

    def mask(self):
        self.masked = True

    def unmask(self):
        self.masked = False

class IterMask(object):

    def is_masked(self):
        return any(elem.is_masked() for elem in self.mask_elem_iter())

class BaseGraph(object):

    def __init__(self):
        self.node_dict = dict()
        self.edge_dict = dict()
        self.path_dict = dict()

    def get_node(self, kind):
        return self.node_dict[kind]

    def get_edge(self, edge_tuple):
        return self.edge_dict[edge_tuple]

    def get_nodes(self):
        return iter(self.node_dict.values())

    def get_edges(self, exclude_inverts=True):
        for edge in self.edge_dict.values():
            if exclude_inverts and edge.inverted:
                continue
            yield edge

    def __iter__(self):
        return iter(self.node_dict.values())

    def __contains__(self, item):
        return item in self.node_dict

class BaseNode(ElemMask):

    def __init__(self, identifier):
        ElemMask.__init__(self)
        self.identifier = identifier

    @abc.abstractmethod
    def get_id(self):
        pass

    def __hash__(self):
        try:
            return self.hash_
        except AttributeError:
            return hash(self.get_id())

    def __lt__(self, other):
        return self.get_id() < other.get_id()

    def __eq__(self, other):
        return (type(other) is type(self)) and (self.get_id() == other.get_id())

class BaseEdge(ElemMask):

    def __init__(self, source, target):
        ElemMask.__init__(self)
        self.source = source
        self.target = target

    def __hash__(self):
        try:
            return self.hash_
        except AttributeError:
            return hash(self.get_id())

    def __str__(self):
        source, target, kind, direction = self.get_id()
        dir_abbrev = direction_to_abbrev[direction]
        return '{0} {3} {2} {3} {1}'.format(source, target, kind, dir_abbrev)

    def get_unicode_str(self):
        """
        Returns a pretty str representation of an edge or metaedge.
        """
        source, target, kind, direction = self.get_id()
        dir_abbrev = direction_to_unicode_abbrev[direction]
        return '{0}{3}{2}{3}{1}'.format(source, target, kind, dir_abbrev)

class BasePath(IterMask):

    def __init__(self, edges):
        assert isinstance(edges, tuple)
        self.edges = edges

    def source(self):
        return self[0].source

    def target(self):
        return self[-1].target

    def get_nodes(self):
        nodes = tuple(edge.source for edge in self)
        nodes = nodes + (self.target(), )
        return nodes

    def inverse_edges(self):
        return tuple(reversed(list(edge.inverse for edge in self)))

    def mask_elem_iter(self):
        for edge in self:
            yield edge
            yield edge.source
        yield self.target()

    def max_overlap(self, others):
        for other in others:
            len_other = len(other)
            if len_other > len(self):
                continue
            if self[:len_other] == other:
                return other
        return None

    def get_unicode_str(self):
        """
        Returns a pretty, unicode, human-readable, and verbose str for a path
        or metapath.
        """
        s = ''
        for edge in self:
            *temp, kind, direction = edge.get_id()
            source = edge.source.name if hasattr(edge, 'name') else edge.source.identifier
            dir_abbrev = direction_to_unicode_abbrev[direction]
            s += '{0}{2}{1}{2}'.format(source, kind, dir_abbrev)
        target = edge.target.name if hasattr(edge, 'name') else edge.target.identifier
        s += target
        return s

    def __iter__(self):
        return iter(self.edges)

    def __getitem__(self, key):
        return self.edges[key]

    def __len__(self):
        return len(self.edges)

    def __hash__(self):
        return hash(self.edges)

    def __eq__(self, other):
        return (type(other) is type(self)) and (self.edges == other.edges)

class MetaGraph(BaseGraph):

    def __init__(self):
        """ """
        BaseGraph.__init__(self)

    @staticmethod
    def from_edge_tuples(metaedge_tuples, kind_to_abbrev=None):
        """Create a new metagraph defined by its edges."""
        metagraph = MetaGraph()
        node_kinds = set()
        for source_kind, target_kind, kind, direction in metaedge_tuples:
            node_kinds.add(source_kind)
            node_kinds.add(target_kind)
        for kind in node_kinds:
            metagraph.add_node(kind)
        for edge_tuple in metaedge_tuples:
            metagraph.add_edge(edge_tuple)

        if kind_to_abbrev is None:
            kind_to_abbrev = hetio.abbreviation.create_abbreviations(metagraph)
        metagraph.set_abbreviations(kind_to_abbrev)

        assert hetio.abbreviation.validate_abbreviations(metagraph)

        return metagraph

    def set_abbreviations(self, kind_to_abbrev):
        """Add abbreviations as an attribute for metanodes and metaedges"""
        self.kind_to_abbrev = kind_to_abbrev
        for kind, metanode in self.node_dict.items():
            metanode.abbrev = kind_to_abbrev[kind]
        for metaedge in self.edge_dict.values():
            abbrev = kind_to_abbrev[metaedge.kind]
            if metaedge.direction == 'forward':
                abbrev = '{}>'.format(abbrev)
            if metaedge.direction == 'backward':
                abbrev = '<{}'.format(abbrev)
            metaedge.kind_abbrev = abbrev

    def add_node(self, kind):
        metanode = MetaNode(kind)
        self.node_dict[kind] = metanode

    def add_edge(self, edge_id):
        """source_kind, target_kind, kind, direction"""
        assert edge_id not in self.edge_dict
        source_kind, target_kind, kind, direction = edge_id
        source = self.get_node(source_kind)
        target = self.get_node(target_kind)

        metaedge = MetaEdge(source, target, kind, direction)
        self.edge_dict[edge_id] = metaedge
        source.edges.add(metaedge)
        metaedge.inverted = False

        if source == target and direction == 'both':
            metaedge.inverse = metaedge
        else:
            inverse_direction = direction_to_inverse[direction]
            inverse_id = target_kind, source_kind, kind, inverse_direction
            assert inverse_id not in self.edge_dict

            inverse = MetaEdge(target, source, kind, inverse_direction)
            self.edge_dict[inverse_id] = inverse
            target.edges.add(inverse)
            metaedge.inverse = inverse
            inverse.inverse = metaedge
            inverse.inverted = True

    def extract_metapaths(self, source_kind, target_kind, max_length):
        source = self.node_dict[source_kind]
        target = self.node_dict[target_kind]

        assert max_length >= 0
        if max_length == 0:
            return []

        metapaths = [self.get_metapath((edge, )) for edge in source.edges]
        previous_metapaths = list(metapaths)
        for depth in range(1, max_length):
            current_metapaths = list()
            for metapath in previous_metapaths:
                for add_edge in metapath.target().edges:
                    new_metapath = self.get_metapath(metapath.edges + (add_edge, ))
                    current_metapaths.append(new_metapath)
            metapaths.extend(current_metapaths)
            previous_metapaths = current_metapaths
        metapaths = [metapath for metapath in metapaths if metapath.target() == target]
        return metapaths

    def get_metapath(self, edges):
        """Store exactly one of each metapath."""
        try:
            return self.path_dict[edges]
        except KeyError:
            assert isinstance(edges, tuple)
            if len(edges) == 0:
                return None

            metapath = MetaPath(edges)
            self.path_dict[edges] = metapath

            inverse_edges = metapath.inverse_edges()
            inverse = MetaPath(inverse_edges)
            self.path_dict[inverse_edges] = inverse

            metapath.inverse = inverse
            inverse.inverse = metapath

            sub_edges = edges[1:]
            if not sub_edges:
                metapath.sub = None
                inverse.sub = None
            else:
                metapath.sub = self.get_metapath(sub_edges)
                inverse.sub = self.get_metapath(inverse_edges[1:])

            return metapath

    def metapath_from_abbrev(self, abbrev):
        """Retrieve a metapath from its abbreviation"""
        metaedges = list()
        metaedge_abbrevs = hetio.abbreviation.metaedges_from_metapath(abbrev)
        for metaedge_abbrev in metaedge_abbrevs:
            metaedge_id = hetio.abbreviation.metaedge_id_from_abbreviation(self, metaedge_abbrev)
            metaedges.append(self.get_edge(metaedge_id))
        return self.get_metapath(tuple(metaedges))

class MetaNode(BaseNode):

    def __init__(self, identifier):
        """ """
        BaseNode.__init__(self, identifier)
        self.edges = set()
        self.hash_ = hash(self)

    def get_id(self):
        return self.identifier

    def __str__(self):
        return str(self.identifier)


class MetaEdge(BaseEdge):

    def __init__(self, source, target, kind, direction):
        """source and target are MetaNodes."""
        BaseEdge.__init__(self, source, target)
        self.kind = kind
        self.direction = direction
        self.hash_ = hash(self)

    def get_id(self):
        """ """
        return self.source.identifier, self.target.identifier, self.kind, self.direction

    def get_abbrev(self):
        return self.source.abbrev + self.kind_abbrev + self.target.abbrev

    def get_standard_abbrev(self):
        """
        Return the standard abbreviation, the abbrevation of the non-inverted
        metaedge with inequality symbols removed. Inequality symbols indicate
        the directionality of directed metaedges and can be removed safely here.
        """
        metaedge = self.inverse if self.inverted else self
        abbrev = metaedge.get_abbrev()
        abbrev = re.sub('[<>]', '', abbrev)
        return abbrev

    def filesystem_str(self):
        s = '{0}{2}{1}-{3}'.format(self.source.abbrev, self.target.abbrev,
                                      self.kind_abbrev, self.direction)
        return s.translate(None, '><')


class MetaPath(BasePath):

    def __init__(self, edges):
        """metaedges is a tuple of edges"""
        assert all(isinstance(edge, MetaEdge) for edge in edges)
        BasePath.__init__(self, edges)

    def __repr__(self):
        s = ''.join(edge.source.abbrev + edge.kind_abbrev for edge in self)
        s += self.target().abbrev
        return s

class Graph(BaseGraph):

    def __init__(self, metagraph, data=dict()):
        """ """
        BaseGraph.__init__(self)
        self.metagraph = metagraph
        self.data = data

    def add_node(self, kind, identifier, name=None, data={}):
        """ """
        if name is None:
            name = identifier
        metanode = self.metagraph.node_dict[kind]
        node = Node(metanode, identifier, name, data)
        node_id = node.get_id()
        assert node_id not in self
        self.node_dict[node_id] = node
        return node

    def add_edge(self, source_id, target_id, kind, direction, data=dict()):
        """source_id and target_id are (metanode, node) tuples"""
        source = self.node_dict[source_id]
        target = self.node_dict[target_id]
        metaedge_id = source.metanode.get_id(), target.metanode.get_id(), kind, direction
        metaedge = self.metagraph.edge_dict[metaedge_id]
        edge = Edge(source, target, metaedge, data)
        self.edge_dict[edge.get_id()] = edge
        edge.inverted = metaedge.inverted

        inverse = Edge(target, source, metaedge.inverse, data)
        inverse_id = inverse.get_id()
        self.edge_dict[inverse_id] = inverse
        inverse.inverted = not edge.inverted

        edge.inverse = inverse
        inverse.inverse = edge

        return edge, inverse

    def unmask(self):
        """Unmask all nodes and edges contained within the graph"""
        for dictionary in self.node_dict, self.edge_dict:
            for value in dictionary.values():
                value.masked = False

    def get_metanode_to_nodes(self):
        metanode_to_nodes = dict()
        for node in self.get_nodes():
            metanode = node.metanode
            metanode_to_nodes.setdefault(metanode, list()).append(node)
        return metanode_to_nodes

    def get_metaedge_to_edges(self, exclude_inverts=False):
        metaedges = self.metagraph.get_edges(exclude_inverts)
        metaedge_to_edges = {metaedge: list() for metaedge in metaedges}
        for edge in self.get_edges(exclude_inverts):
            metaedge_to_edges[edge.metaedge].append(edge)
        return metaedge_to_edges


class Node(BaseNode):

    def __init__(self, metanode, identifier, name, data):
        """ """
        BaseNode.__init__(self, identifier)
        self.metanode = metanode
        self.name = name
        self.data = data
        self.edges = {metaedge: set() for metaedge in metanode.edges}

    def get_id(self):
        return self.metanode.identifier, self.identifier

    def get_edges(self, metaedge, exclude_masked=True):
        """
        Returns the set of edges incident to self of the specified metaedge.
        """
        if exclude_masked:
            edges = set()
            for edge in self.edges[metaedge]:
                if edge.masked or edge.target.masked:
                    continue
                edges.add(edge)
        else:
            edges = self.edges[metaedge]
        return edges

    def __repr__(self):
        return '{!s}({!r})'.format(self.__class__, self.__dict__)

    def __str__(self):
        return '{}::{}'.format(*self.get_id())

class Edge(BaseEdge):

    def __init__(self, source, target, metaedge, data):
        """source and target are Node objects. metaedge is the MetaEdge object
        representing the edge
        """
        BaseEdge.__init__(self, source, target)
        self.metaedge = metaedge
        self.data = data
        self.source.edges[metaedge].add(self)

    def get_id(self):
        return self.source.get_id(), self.target.get_id(), self.metaedge.kind, self.metaedge.direction

class Path(BasePath):

    def __init__(self, edges):
        """potentially metapath should be an input although it can be calculated"""
        BasePath.__init__(self, edges)

    def __repr__(self):
        s = ''
        for edge in self:
            dir_abbrev = direction_to_abbrev[edge.metaedge.direction]
            s += '{0} {1} {2} {1} '.format(edge.source, dir_abbrev, edge.metaedge.kind)
        s = '{}{}'.format(s, self.target())
        return s
