""" Sphinx extension to generate documention from XML schemas.  Known
to be woefully imcomplete, probably buggy, terrible error handling,
but it *works* for the subset of XML schema we use in Bcfg2.

Provides the following directives:

* ``.. xml:schema:: <filename>``: Document an XML schema
* ``.. xml:type:: <name>``: Document a complexType or simpleType
* ``.. xml:group:: <name>``: Document an element group
* ``.. xml:attributegroup:: <name>``: Document an attributeGroup
* ``.. xml:element:: <name>``: Document an XML element

Each directive supports the following options:

* ``:namespace: <ns>``: Specify the namespace of the given entity
* ``:nochildren:``: Do not generate documentation for child entities
* ``:noattributegroups:``: Do not generate documentation about
  attribute groups
* ``:nodoc:``: Do not include the documentation included in the entity
  annotation
* ``:notext:``: Do not generate documentation about the text content
  of the entity
* ``:onlyattrs: <attr>,<attr>``: Only generate documentation about the
  comma-separated list of attributes given
* ``:requiredattrs: <attr>,attr>``: Claim that the attributes named in
  the given comma-separated list are required, even if they are not
  flagged as such in the schema.
* ``:linktotype: [<type>,<type>]``: If used as a flag, link to
  documentation on all child types and elements.  If a list is given,
  only link to those types given.  (The default is to generate full
  inline docs for those types.)
* ``:noautodep: [<name>,<name>]``: Do not automatically generate docs
  for any dependent entities.
* ``:inlinetypes: <type>,<type>``: Override a default ``:linktotype:``
  setting for the given types.

Provides the following roles to link to the objects documented above:

* ``:xml:schema:`<name>```: Link to an XML schema
* ``:xml:type:`<name>```: Link to a complexType or simpleType
* ``:xml:group:`<name>```: Link to an element group
* ``:xml:attributegroup:`<name>```: Link to an attributeGroup
* ``:xml:element:`<name>```: Link to an element
* ``:xml:attribute:`<context>:<name>```: Link to the attribute in the
  given context.  The context is the name of the containing object,
  e.g., the parent attributeGroup, element, or complexType.
* ``:xml:datatype:`<name>```: Link to a built-in XML data type.

Note that the entity being linked to does not need to have been
explicitly documented with a directive; e.g., if you document a schema
that contains a complexType, you can link to that type without having
used the ``xml:type::`` directive.

Note also that it's far more reliable to link to a complexType than an
element, since element name collisions are fairly common.  You should
avoid type name collisions whenever possible to maximize usability of
this extension.

There are two configuration items that may be added to conf.py:

* ``xmlschema_path`` gives the base path to all XML schemas.
* ``xmlschema_datatype_url`` gives a string pattern that will be used
  to generate links to built-in XML types.  It must contain a single
  ``%s``, which will be replaced by the name of the type.
"""

import os
import operator
import lxml.etree
from docutils import nodes
from sphinx import addnodes, roles
from docutils.statemachine import ViewList
from docutils.parsers.rst import directives
from sphinx.util.nodes import make_refnode, split_explicit_title, \
    nested_parse_with_titles
from sphinx.util.compat import Directive
from sphinx.domains import ObjType, Domain

try:
    from new import classobj
except ImportError:
    classobj = type

XS = "http://www.w3.org/2001/XMLSchema"
XS_NS = "{%s}" % XS
NSMAP = dict(xs=XS)


def comma_split(opt):
    return opt.split(",")


def flag_or_split(opt):
    try:
        return opt.split(",")
    except AttributeError:
        return True


class _XMLDirective(Directive):
    """ Superclass for the other XML schema directives. """
    required_arguments = 1
    option_spec = dict(namespace=directives.unchanged,
                       nochildren=directives.flag,
                       noattributegroups=directives.flag,
                       nodoc=directives.flag,
                       notext=directives.flag,
                       onlyattrs=comma_split,
                       requiredattrs=comma_split,
                       linktotype=flag_or_split,
                       noautodep=flag_or_split,
                       inlinetypes=comma_split)
    types = []

    def run(self):
        name = self.arguments[0]
        env = self.state.document.settings.env
        reporter = self.state.memo.reporter
        ns_name = self.options.get('namespace')
        try:
            ns_uri = env.xmlschema_namespaces[ns_name]
        except KeyError:
            # URI given as namespace
            ns_uri = ns_name
        etype = None
        for etype in self.types:
            try:
                entity = env.xmlschema_entities[ns_uri][etype][name]
                break
            except KeyError:
                pass
        else:
            reporter.error("No XML %s %s found" %
                           (" or ".join(self.types), name))
            return []
        documentor = XMLDocumentor(entity, env, self.state, name=name,
                                   ns_uri=ns_uri,
                                   include=self.process_include(),
                                   options=self.process_options())
        return documentor.document()

    def process_include(self):
        return dict(children='nochildren' not in self.options,
                    attributegroups='noattributegroups' not in self.options,
                    doc='nodoc' not in self.options,
                    text='notext' not in self.options)

    def process_options(self):
        return dict(onlyattrs=self.options.get('onlyattrs'),
                    requiredattrs=self.options.get('requiredattrs', []),
                    linktotype=self.options.get('linktotype', []),
                    noautodep=self.options.get('noautodep', False),
                    inlinetypes=self.options.get('inlinetypes', []))


def XMLDirective(types):
    class cls(_XMLDirective):
        pass

    cls.__name__ = 'XML%sDirective' % types[0]
    cls.types = types
    return cls


class XMLDocumentor(object):
    def __init__(self, entity, environment, state, name=None, ns_uri=None,
                 parent=None, include=None, options=None):
        self.entity = entity
        self.env = environment
        self.entities = self.env.xmlschema_entities
        self.namespaces = self.env.xmlschema_namespaces
        self.namespaces_by_uri = self.env.xmlschema_namespaces_by_uri
        self.state = state
        self.include = include
        self.options = options
        self.app = self.env.app
        self.reporter = self.state.memo.reporter

        if name is None:
            self.ns_uri = ns_uri
            self.fqname = self.entity.get("name")
            self.ns_name, self.name = self.split_ns(self.fqname)
            if self.ns_uri is None and self.ns_name is not None:
                self.ns_uri = self.namespaces[self.ns_name]
        else:
            self.ns_uri = ns_uri
            self.ns_name = self.namespaces_by_uri[self.ns_uri]
            self.name = name
            if self.ns_name:
                self.fqname = "%s:%s" % (self.ns_name, self.name)
            else:
                self.fqname = name
        self.tname = nodes.strong(self.fqname, self.fqname)
        self.tag = self.entity.tag[len(XS_NS):]
        self.type = tag2type(self.tag)
        self.parent = parent
        if self.parent is None:
            self.dependencies = []
            self.documented = []
        else:
            self.dependencies = self.parent.dependencies
            self.documented = self.parent.documented

    def document(self):
        eid = (self.tag, self.fqname)
        if eid in self.documented:
            return [build_paragraph(get_xref(self.tag, eid[1]))]
        else:
            self.documented.append(eid)

        rv = [self.target_node(self.tag, self.ns_name, self.name)]

        data = addnodes.desc(objtype=self.tag)
        targetid = get_target_id(self.tag, self.ns_name, self.name)
        header = addnodes.desc_signature('', '',
                                         first=True,
                                         ids=[targetid])

        if self.include['doc']:
            header.extend([nodes.emphasis(self.tag, self.tag),
                          text(" "), self.tname])
            data.append(header)
        contents = nodes.definition()
        if self.include['doc']:
            contents.append(self.get_doc(self.entity))
        contents.extend(getattr(self, "document_%s" % self.tag)())
        data.append(contents)
        rv.append(data)

        if self.parent is None:
            # avoid adding duplicate dependencies
            added = [(self.type, self.name)]
            for typ, name, entity in self.dependencies:
                if not name:
                    name = entity.get('name')
                if (typ, name) in added:
                    continue
                ns_name, name = self.split_ns(name)
                ns_uri = self.namespaces[ns_name]
                if not entity:
                    try:
                        entity = self.entities[ns_uri][typ][name]
                    except KeyError:
                        self.app.warn("Dependency %s not found in schemas" %
                                      get_target_id(typ, ns_name, name))
                        continue
                doc = self.get_documentor(entity, name=name, ns_uri=ns_uri)
                rv.extend(doc.document())
                added.append((typ, name))
        return rv

    def document_schema(self):
        try:
            element = self.entity.xpath("xs:element", namespaces=NSMAP)[0]
            ns, name = self.split_ns(element.get("name"))
            doc = self.get_documentor(element, name=name,
                                      ns_uri=self.namespaces[ns])
            return doc.document()
        except IndexError:
            # no top-level element or group -- just a list of
            # (abstract) complexTypes?
            rv = []
            for ctype in self.entity.xpath("xs:complexType", namespaces=NSMAP):
                ns, name = self.split_ns(ctype.get("name"))
                doc = self.get_documentor(ctype, name=name,
                                          ns_uri=self.namespaces[ns])
                rv.extend(doc.document())
            return rv

    def document_group(self):
        rv = nodes.definition_list()
        try:
            (children, groups) = \
                self.get_child_elements(self.entity, nodeclass=nodes.paragraph)
        except TypeError:
            return [build_paragraph(nodes.strong("Any", "Any"),
                                    " arbitrary element allowed")]

        append_node(rv, nodes.term, text("Elements:"))
        append_node(rv, nodes.definition, *children)
        if len(groups):
            append_node(rv, nodes.term, text("Element groups:"))
            append_node(rv, nodes.definition, *groups)
        return rv

    def document_element(self):
        fqtype = self.entity.get("type")
        if fqtype:
            (etype_ns, etype) = self.split_ns(fqtype)
            ns_uri = self.get_namespace_uri(etype_ns)
            values = self.get_values_from_type()
            if values != "Any":
                return [build_paragraph(
                        self.tname,
                        " takes only text content, which may be the ",
                        "following values: ",
                        values)]
            elif etype in self.entities[ns_uri]["complexType"]:
                if ((self.options['linktotype'] is True or
                     self.name in self.options['linktotype'] or
                     etype in self.options['linktotype'] or
                     fqtype in self.options['linktotype']) and
                    self.name not in self.options['inlinetypes'] and
                    etype not in self.options['inlinetypes']):
                    self.add_dep('complexType', fqtype, None)
                    return [build_paragraph("Type: ",
                                            get_xref("type", fqtype))]

                typespec = self.entities[ns_uri]["complexType"][etype]
                doc = self.get_documentor(typespec,
                                          name=self.entity.get("name"))
                rv = [self.target_node("complexType", etype_ns, etype)]
                if self.include['doc'] and not self.get_doc(self.entity):
                    rv.append(self.get_doc(typespec))
                rv.extend(doc.document_complexType())
                return rv
            else:
                self.reporter.error("Unknown element type %s" % fqtype)
                return []
        else:
            rv = []
            typespec = self.entity.xpath("xs:complexType", namespaces=NSMAP)[0]
            if self.include['doc'] and not self.get_doc(self.entity):
                rv.append(self.get_doc(typespec))
            if typespec is not None:
                rv = [self.target_node("complexType", self.ns_name, self.name)]
                doc = self.get_documentor(typespec)
                rv.extend(doc.document_complexType())
            return rv

    def document_complexType(self):
        rv = nodes.definition_list()

        try:
            content = self.entity.xpath("xs:simpleContent",
                                        namespaces=NSMAP)[0]
            base = content.xpath("xs:extension|xs:restriction",
                                 namespaces=NSMAP)[0]
            attr_container = base
        except IndexError:
            base = None
            attr_container = self.entity

        ##### ATTRIBUTES #####
        table, tbody = self.get_attr_table()
        attrs = self.get_attrs(attr_container)
        if attrs:
            tbody.extend(attrs)

        foreign_attr_groups = nodes.bullet_list()
        for agroup in attr_container.xpath("xs:attributeGroup",
                                           namespaces=NSMAP):
            # if the attribute group is in another namespace, just
            # link to it
            ns, name = self.split_ns(agroup.get('ref'))
            if ns != self.ns_name:
                append_node(
                    foreign_attr_groups,
                    nodes.list_item,
                    build_paragraph(get_xref(tag2type("attributeGroup"),
                                             ":".join([ns, name]))))
            else:
                tbody.extend(self.get_attrs(
                        self.entities['attributeGroup'][name]))

        if len(tbody):
            append_node(rv, nodes.term, text("Attributes:"))
            append_node(rv, nodes.definition, table)
        if self.include['attributegroups'] and len(foreign_attr_groups):
            append_node(rv, nodes.term, text("Attribute groups:"))
            append_node(rv, nodes.definition, foreign_attr_groups)

        ##### ELEMENTS #####
        if self.include['children']:
            # todo: distinguish between elements that may occur and
            # elements that must occur
            try:
                (children, groups) = self.get_child_elements(self.entity)
            except TypeError:
                children = None
                groups = None
                rv.append(build_paragraph(nodes.strong("Any", "Any"),
                                          " arbitrary child elements allowed"))
            if children:
                append_node(rv, nodes.term, text("Child elements:"))
                append_node(rv, nodes.definition,
                            build_node(nodes.bullet_list, *children))

            if groups:
                append_node(rv, nodes.term, text("Element groups:"))
                append_node(rv, nodes.definition, *groups)

        ##### TEXT CONTENT #####
        if self.include['text']:
            if self.entity.get("mixed", "false").lower() == "true":
                append_node(rv, nodes.term, text("Text content:"))
                append_node(rv, nodes.definition,
                            build_paragraph(self.get_values_from_simpletype()))
            elif base is not None:
                append_node(rv, nodes.term, text("Text content:"))
                append_node(
                    rv, nodes.definition,
                    build_paragraph(self.get_values_from_simpletype(content)))

        return [rv]

    def document_attributeGroup(self):
        attrs = self.get_attrs(self.entity)
        if attrs:
            table, tbody = self.get_attr_table()
            tbody.extend(attrs)
            return [table]
        else:
            return []

    def get_attr_table(self):
        atable = nodes.table()
        atgroup = build_node(nodes.tgroup('', cols=5),
                             nodes.colspec(colwidth=10),
                             nodes.colspec(colwidth=50),
                             nodes.colspec(colwidth=20),
                             nodes.colspec(colwidth=10),
                             nodes.colspec(colwidth=10),
                             nodes.thead('',
                                         build_table_row("Name", "Description",
                                                         "Values", "Required",
                                                         "Default")))
        atable.append(atgroup)
        atable_body = nodes.tbody()
        atgroup.append(atable_body)
        return (atable, atable_body)

    def get_child_elements(self, el, nodeclass=None):
        """ returns a tuple of (child element nodes, element group
        nodes).  HOWEVER, if _any_ child is allowed, returns True. """
        children = []
        groups = []
        if nodeclass is None:
            nodeclass = nodes.list_item

        if el.xpath("xs:any", namespaces=NSMAP):
            return True

        for child in el.xpath("xs:element", namespaces=NSMAP):
            node = nodeclass()
            if child.get('ref'):
                node.append(build_paragraph(get_xref('element',
                                                     child.get('ref'))))
            else:
                # child element given inline
                doc = self.get_documentor(child, name=child.get('name'))
                node.extend(doc.document())
            children.append(node)

        for group in el.xpath("xs:group", namespaces=NSMAP):
            if group.get('ref'):
                name = group.get('ref')
                node = nodeclass()
                node.append(build_paragraph(get_xref('group', name)))
                self.add_dep('group', name, None)
                groups.append(node)
            else:
                rv = self.get_child_elements(group, nodeclass=nodeclass)
                try:
                    children.extend(rv[0])
                    groups.extend(rv[1])
                except TypeError:
                    return rv

        for container in el.xpath("xs:all|xs:choice|xs:sequence",
                                  namespaces=NSMAP):
            rv = self.get_child_elements(container, nodeclass=nodeclass)
            try:
                children.extend(rv[0])
                groups.extend(rv[1])
            except TypeError:
                return rv
        return (children, groups)

    def get_documentor(self, entity, name=None, ns_uri=None):
        if name is None:
            name = self.name
        if ns_uri is None:
            ns_uri = self.ns_uri
        return XMLDocumentor(entity, self.env, self.state, name=name,
                             ns_uri=ns_uri, parent=self, options=self.options,
                             include=self.include)

    def get_attrs(self, el, context=None):
        cnode = el
        while context is None and cnode is not None:
            context = cnode.get('name')
            cnode = cnode.getparent()

        rows = []
        for attr in el.xpath("xs:attribute[@name]", namespaces=NSMAP):
            name = attr.get("name")
            if self.ns_name:
                fqname = "%s:%s" % (self.ns_name, name)
            else:
                fqname = name
            if (self.options['onlyattrs'] and
                name not in self.options['onlyattrs'] and
                fqname not in self.options['onlyattrs']):
                continue
            tag = attr.tag[len(XS_NS):]
            row = [build_paragraph(self.target_node(tag, self.ns_name, context,
                                                    name),
                                   nodes.literal(fqname, fqname))]
            row.append(self.get_doc(attr))
            if attr.get("type") is not None:
                row.append(build_paragraph(
                        self.get_values_from_type(entity=attr)))
            else:
                try:
                    atype = attr.xpath("xs:simpleType", namespaces=NSMAP)[0]
                    row.append(self.get_values_from_simpletype(atype))
                except IndexError:
                    # todo: warn about no type found
                    pass
            reqd = 0
            if (name in self.options['requiredattrs'] or
                attr.get("use", "optional") == "required"):
                row.append("Yes")
                reqd = 1
            else:
                row.append("No")
            default = attr.get("default")
            if default is None:
                row.append("None")
            else:
                row.append(nodes.literal(default, default))
            # we record name and required separately to make sorting
            # easier
            rows.append((name, reqd, build_table_row(*row)))
        rows.sort(key=operator.itemgetter(0))
        rows.sort(key=operator.itemgetter(1), reverse=True)
        if not self.options['onlyattrs'] or '*' in self.options['onlyattrs']:
            try:
                anyattr = el.xpath("xs:anyAttribute", namespaces=NSMAP)[0]
                rows.append((None, None,
                             build_table_row('*', self.get_doc(anyattr),
                                             "Any", "No", "None")))
            except IndexError:
                pass
        return [r[2] for r in rows]

    def get_values_from_type(self, entity=None, typeattr='type'):
        if entity is None:
            entity = self.entity
        ns_name, name = self.split_ns(entity.get(typeattr))
        ns_uri = self.get_namespace_uri(ns_name, entity=entity)
        if ns_uri == XS:
            return self.get_builtin_type(name)
        elif name in self.entities[ns_uri]['simpleType']:
            return self.get_values_from_simpletype(
                self.entities[ns_uri]['simpleType'][name])
        else:
            return "Any"

    def get_builtin_type(self, vtype):
        if vtype == "boolean":
            return get_value_list(["true", "false"])
        else:
            return get_datatype_ref(vtype, vtype,
                                    self.app.config.xmlschema_datatype_url)

    def get_doc(self, el):
        try:
            return self.parse(el.xpath("xs:annotation/xs:documentation",
                                       namespaces=NSMAP)[0].text)
        except IndexError:
            return build_paragraph('')

    def parse(self, text):
        node = nodes.paragraph()
        vl = ViewList()
        for line in text.splitlines():
            vl.append(line, '<xmlschema>')
        nested_parse_with_titles(self.state, vl, node)
        try:
            return node[0]
        except IndexError:
            return build_paragraph(text)

    def split_ns(self, name):
        try:
            (ns, name) = name.split(":")
        except ValueError:
            ns = self.ns_name
        return (ns, name)

    def get_values_from_simpletype(self, entity=None):
        if entity is None:
            entity = self.entity
        # todo: xs:union, xs:list
        try:
            restriction = entity.xpath("xs:restriction|xs:extension",
                                       namespaces=NSMAP)[0]
        except IndexError:
            return "Any"
        doc = self.get_doc(restriction)
        if len(doc) == 1 and len(doc[0]) == 0:
            # if get_doc returns a paragraph node with an empty Text
            # node
            enum = [e.get("value")
                    for e in restriction.xpath("xs:enumeration",
                                               namespaces=NSMAP)]
            if len(enum):
                return get_value_list(enum)
            else:
                return self.get_values_from_type(entity=restriction,
                                                 typeattr='base')
        else:
            return doc

    def add_dep(self, typ, name, entity):
        try:
            if name in self.options['noautodep']:
                return
        except TypeError:
            if self.options['noautodep']:
                return
        self.dependencies.append((typ, name, entity))

    def target_node(self, tag, ns, *extra):
        targetid = get_target_id(tag, ns, *extra)
        fqname = targetid[len(tag) + 1:]
        rv = nodes.target('', '', ids=[targetid])
        self.add_domain_data(tag2type(tag), fqname,
                             (self.env.docname, targetid))
        return rv

    def add_domain_data(self, typ, key, data):
        if key not in self.env.domaindata['xml'][typ]:
            self.env.domaindata['xml'][typ][key] = data

    def get_namespace_uri(self, ns_name, entity=None):
        if entity is None:
            entity = self.entity
        xs_ns = get_xs_ns(entity)
        if ns_name == xs_ns:
            return XS
        else:
            return self.namespaces[ns_name]


def tag2type(tag):
    if tag in ['complexType', 'simpleType']:
        return 'type'
    elif tag == 'attributeGroup':
        return 'attributegroup'
    return tag


def text(txt):
    return nodes.Text(txt, txt)


def append_node(parent, cls_or_node, *contents):
    parent.append(build_node(cls_or_node, *contents))


def build_node(cls_or_node, *contents):
    if isinstance(cls_or_node, (type, classobj)):
        rv = cls_or_node()
    else:
        rv = cls_or_node
    rv.extend(contents)
    return rv


def get_xref(typ, target, title=None):
    if title is None:
        title = target
    ref = addnodes.pending_xref(title,
                                reftype=typ,
                                refdomain="xml",
                                reftarget=target)
    ref.append(nodes.literal(title, title))
    return ref


def build_table_row(*vals):
    rv = nodes.row('')
    for val in vals:
        if isinstance(val, nodes.Node):
            node = val
        else:
            node = nodes.paragraph(val, val)
        rv.append(nodes.entry(node, node))
    return rv


def build_paragraph(*args):
    """ convenience method to build a paragraph node """
    rv = nodes.paragraph()
    for content in args:
        if isinstance(content, nodes.Node):
            rv.append(content)
        else:
            rv.append(text(content))
    return rv


def get_target_id(etype, ns_name, *extra):
    if ns_name:
        return ":".join([etype, ns_name] + list(extra))
    else:
        return ":".join([etype] + list(extra))


def get_value_list(vals):
    rv = nodes.paragraph()
    if vals:
        rv.append(nodes.literal(vals[0], vals[0]))
        for i in range(1, len(vals)):
            rv.append(text(" | "))
            rv.append(nodes.literal(vals[i], vals[i]))
    return rv


def get_xs_ns(el):
    return get_namespace_name(el, XS)


def get_namespace_name(el, ns_uri):
    for name, ns in el.nsmap.items():
        if ns == ns_uri:
            return name
    return None


def get_datatype_ref(title, target, baseurl):
    return build_node(nodes.reference('', '', refuri=baseurl % target),
                      nodes.literal(title, title))


class XMLDatatypeRole(object):
    def __init__(self, baseurl):
        self.baseurl = baseurl

    def __call__(self, name, rawtext, text, lineno, inliner, options={},
                 content=[]):
        has_explicit_title, title, target = split_explicit_title(text)
        return [get_datatype_ref(title, target, self.baseurl)], []


class XMLXRefRole(roles.XRefRole):
    def __init__(self, typ, **kwargs):
        roles.XRefRole.__init__(self, **kwargs)
        self.type = typ

    def process_link(self, env, refnode, has_explicit_title, title, target):
        if (self.type == 'attribute' and
            not has_explicit_title and
            ':' in title):
            title = title.split(':')[-1]
        return roles.XRefRole.process_link(self, env, refnode,
                                           has_explicit_title, title, target)


class XMLDomain(Domain):
    name = "xml"
    label = "XML"

    types = dict(schema=['schema'],
                 type=['complexType', 'simpleType'],
                 group=['group'],
                 attributegroup=['attributeGroup'],
                 element=['element'],
                 attribute=None)

    object_types = dict([(t, ObjType("XML %s" % t.title(), t))
                         for t in types.keys()])
    directives = dict([(t, XMLDirective(h))
                        for t, h in types.items() if h is not None])
    roles = dict([(t, XMLXRefRole(t)) for t in types.keys()])
    dangling_warnings = dict([(t, "unknown XML %s: %%(target)s" % t)
                              for t in types.keys()])
    initial_data = dict([(t, dict()) for t in types.keys()])
    data_version = 3

    def clear_doc(self, docname):
        to_del = []
        for dtype in self.types.keys():
            for key, (doc, _) in self.data[dtype].items():
                if doc == docname:
                    to_del.append((dtype, key))
        for dtype, key in to_del:
            del self.data[dtype][key]

    def resolve_xref(self, env, fromdocname, builder, typ, target, node,
                     contnode):
        if typ in ['complexType', 'simpleType']:
            typ = 'type'
        if target in self.data[typ]:
            docname, labelid = self.data[typ][target]
        else:
            return None
        return make_refnode(builder, fromdocname, docname,
                            labelid, contnode)

    def get_objects(self):
        for dtype in self.types.keys():
            for name, (docname, tgtid) in self.data[dtype].items():
                yield (name, name, dtype, docname, tgtid,
                       self.object_types[dtype].attrs['searchprio'])


def setup(app):
    app.add_config_value('xmlschema_path', '.', False)
    app.add_config_value('xmlschema_datatype_url',
                         'http://www.w3.org/TR/xmlschema-2/#%s', False)
    app.add_domain(XMLDomain)
    app.connect('builder-inited', load_xml_schemas)
    app.connect('builder-inited', add_xml_datatype_role)


def add_xml_datatype_role(app):
    app.add_role_to_domain('xml', 'datatype',
                           XMLDatatypeRole(app.config.xmlschema_datatype_url))


def load_xml_schemas(app):
    entities = dict()
    entities[None] = dict(schema=dict(),
                          group=dict(),
                          attributeGroup=dict(),
                          element=dict(),
                          simpleType=dict(),
                          complexType=dict())
    namespaces = dict()
    namespaces_by_uri = dict()
    schemapath = os.path.abspath(os.path.join(app.builder.env.srcdir,
                                              app.config.xmlschema_path))
    for root, _, files in os.walk(schemapath):
        for fname in files:
            if not fname.endswith(".xsd"):
                continue
            path = os.path.join(root, fname)
            relpath = path[len(schemapath):].strip("/")
            schema = lxml.etree.parse(path).getroot()

            ns = schema.get("targetNamespace")
            ns_name = get_namespace_name(schema, ns)
            if ns_name not in namespaces:
                namespaces[ns_name] = ns
            if ns not in namespaces_by_uri:
                namespaces_by_uri[ns] = ns_name

            if ns not in entities:
                entities[ns] = dict(schema=dict(),
                                    group=dict(),
                                    attributeGroup=dict(),
                                    element=dict(),
                                    simpleType=dict(),
                                    complexType=dict())
            # schemas don't require namespaces to be identified
            # uniquely, but we let the user identify them either with
            # or without the namespace
            entities[None]['schema'][relpath] = schema
            entities[ns]['schema'][relpath] = schema
            for entity in schema.xpath("//xs:*[@name]", namespaces=NSMAP):
                tag = entity.tag[len(XS_NS):]
                if tag in entities[ns]:
                    entities[ns][tag][entity.get("name")] = entity
    app.builder.env.xmlschema_namespaces = namespaces
    app.builder.env.xmlschema_namespaces_by_uri = namespaces_by_uri
    app.builder.env.xmlschema_entities = entities
