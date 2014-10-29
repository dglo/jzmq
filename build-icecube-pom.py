#!/usr/bin/env python


import sys
from lxml import etree, objectify

TOP_KEEP = ("modelVersion", "groupId", "artifactId", "packaging", "name",
           "description", "url", "licenses", "developers")
TOP_IGNORE = ("parent", "scm", "dependencies")

PROFILE_KEEP = ("Linux", "Windows", "Mac", "os-distro", "zmq-version")
PROFILE_IGNORE = ("release", "deploy-local-maven")

BUILD_PLUGIN_KEEP = ("maven-assembly-plugin", )
BUILD_PLUGIN_IGNORE = ("maven-gpg-plugin", "buildnumber-maven-plugin",
                       "maven-release-plugin", "maven-scm-plugin",
                       "maven-jar-plugin", "maven-surefire-plugin",
                       "maven-shade-plugin", "maven-deploy-plugin",
                       "maven-source-plugin", "maven-javadoc-plugin",
                       )

MAC_OS_NAME = "Darwin"

MAVEN_REPO_URL = "scp://block.wipac.wisc.edu//var/www/html/maven2/repository"

def add_dependencies(elem):
    top = etree.SubElement(elem, "dependencies")
    dep = etree.SubElement(top, "dependency")

    pairs = (("groupId", "junit"),
             ("artifactId", "junit"),
             ("version", "${junit.version}"),
             ("scope", "test")
             )

    for p in pairs:
        node = etree.SubElement(dep, p[0])
        node.text = p[1]

def add_distribution_mgmt(elem):
    top = etree.SubElement(elem, "distributionManagement")
    repo = etree.SubElement(top, "repository")

    rid = etree.SubElement(repo, "id")
    rid.text = "icecube-maven-repository"

    rurl = etree.SubElement(repo, "url")
    rurl.text = MAVEN_REPO_URL

def add_plugin_compiler(elem):
    add_plugin_generic(elem, "maven-compiler-plugin",
                       (("debug", "true"),
                        ("encoding", "${project.build.sourceEncoding}")))

def add_plugin_generic(elem, name, cfgPairs):
    plug = etree.SubElement(elem, "plugin")

    aid = etree.SubElement(plug, "artifactId")
    aid.text = name

    vers = etree.SubElement(plug, "version")
    vers.text = "${%s.version}" % name

    if cfgPairs is None or len(cfgPairs) == 0:
        return

    cfg = etree.SubElement(plug, "configuration")
    for p in cfgPairs:
        node = etree.SubElement(cfg, p[0])
        node.text = p[1]

def add_plugin_surefire(elem):
    argline = "-Djava.library.path=${native.library-path.resolved}"
    add_plugin_generic(elem, "maven-surefire-plugin",
                       (("forkMode", "once"), ("argLine", argline)))

def add_wagon_ssh(elem):
    exts = etree.SubElement(elem, "extensions")
    ext = etree.SubElement(exts, "extension")

    pairs = (("groupId", "org.apache.maven.wagon"),
             ("artifactId", "wagon-ssh"),
             ("version", "LATEST"),
         )

    for pair in pairs:
        node = etree.SubElement(ext, pair[0])
        node.text = pair[1]

def deepcopy(elem, newroot):
    oldtag = prune_tag(elem)
    if not isinstance(oldtag, basestring):
        newroot.append(etree.Comment(elem.text))
        return

    newelem = etree.SubElement(newroot, oldtag)
    if elem.text is not None:
        newelem.text = elem.text
    for attr in elem.keys():
        newelem.set(attr, elem[attr])

    for kid in elem:
        deepcopy(kid, newelem)

def fix_build_plugin(bldplug, oldelem):
    others = []
    for node in oldelem:
        tag = prune_tag(node)
        if tag == "artifactId":
            if node.text in BUILD_PLUGIN_IGNORE:
                return
            if not node.text in BUILD_PLUGIN_KEEP:
                print >>sys.stderr, "Ignoring unknown build plugin %s" % \
                    node.text
                return

        others.append(node)

    newelem = etree.SubElement(bldplug, "plugin")

    for p in others:
        deepcopy(p, newelem)

def fix_profile(profiles, oldelem):
    pid = None
    props = None
    pother = []
    for kid in oldelem:
        tag = prune_tag(kid)
        if tag == "id":
            pid = kid
        elif tag == "properties":
            props = kid
        else:
            pother.append(kid)

    if pid is None:
        print >>sys.stderr, "Ignoring <profile> without <id>"
        return False

    if pid.text in PROFILE_IGNORE:
        return False

    if not pid.text in PROFILE_KEEP and pid.text != "Mac":
        print >>sys.stderr, "Ignoring <profile> with id %s" % pid.text
        return False

    prof = etree.SubElement(profiles, "profile")
    deepcopy(pid, prof)

    for p in pother:
        deepcopy(p, prof)

    if pid.text != "Mac":
        if props is not None:
            deepcopy(props, prof)
    elif props is None:
        print >>sys.stderr, "Mac <profile> has no <properties>"
    else:
        newprops = etree.SubElement(prof, "properties")
        for kid in props:
            tag = prune_tag(kid)
            if tag != "native.os":
                deepcopy(kid, newprops)
            else:
                os = etree.SubElement(newprops, "native.os")
                if kid.text != MAC_OS_NAME:
                    print >>sys.stderr, \
                        "Changing Mac <native.os> from %s to %s" % \
                        (kid.text, MAC_OS_NAME)
                os.text = MAC_OS_NAME

def fix_properties(props, oldelem):
    tag = prune_tag(oldelem)
    if tag.endswith(".version"):
        if tag[:-8] in BUILD_PLUGIN_IGNORE:
            return (None, None)
        elif tag == "maven-buildnumber-plugin.version" and \
        "buildnumber-maven-plugin" in BUILD_PLUGIN_IGNORE:
            # nonstandard version name
            return (None, None)

    newprop = etree.SubElement(props, tag)
    newprop.text = oldelem.text

    return (tag, oldelem.text)

def prune_tag(elem):
    if hasattr(elem.tag, 'find'):
        i = elem.tag.find('}')
        if i >= 0:
            return elem.tag[i+1:]
    return elem.tag

def main():
    parser = etree.XMLParser(remove_blank_text=True)
    oldpom = etree.parse("pom.xml", parser)

    root = oldpom.getroot()

    newpom = etree.Element(root.tag)
    newpom.tag = prune_tag(newpom)

    need_dependencies = True
    for top in oldpom.getroot():
        tag = prune_tag(top)
        if tag in TOP_KEEP:
            deepcopy(top, newpom)
        elif tag in TOP_IGNORE:
            pass
        elif tag == "version":
            newv = etree.SubElement(newpom, tag)
            newv.text = top.text + "-ICECUBE"
        elif tag == "properties":
            found = {}
            newprops = etree.SubElement(newpom, tag)
            for p in top:
                (name, val) = fix_properties(newprops, p)
                if name is not None:
                    found[name] = val

            myversions = (("maven-compiler-plugin.version", "2.3"),
                          ("maven-surefire-plugin.version", "2.16"),
                          )
            for v in myversions:
                if found.has_key(v[0]):
                    if found[v[0]] != v[1]:
                        print >>sys.stderr, \
                            "Not overwriting %s version %s with %s" % \
                            (v[0], found[v[0]], v[1])
                    continue

                newp = etree.SubElement(newprops, v[0])
                newp.text = v[1]

            if need_dependencies:
                # insert dependencies after properties
                add_dependencies(newpom)
                need_dependencies = False

        elif tag == "profiles":
            newprof = etree.SubElement(newpom, tag)
            for p in top:
                fix_profile(newprof, p)
        elif tag == "build":
            newbld = etree.SubElement(newpom, tag)
            add_wagon_ssh(newbld)

            newplug = etree.SubElement(newbld, "plugins")
            add_plugin_compiler(newplug)
            add_plugin_surefire(newplug)

            for node in top:
                tag = prune_tag(node)
                if tag != "plugins":
                    print >> sys.stderr, "Ignoring build node <%s>" % tag
                    continue

                for p in node:
                    ptag = prune_tag(p)
                    if ptag != "plugin":
                        print >>sys.stderr, "Ignoring build/plugin node %s" % \
                            ptag
                        continue

                    fix_build_plugin(newplug, p)
        else:
            print >>sys.stderr, "Ignoring top-level tag <%s>" % prune_tag(top)

    if need_dependencies:
        # if we haven't yet inserted dependencies, do it now
        add_dependencies(newpom)
        need_dependencies = False

    add_distribution_mgmt(newpom)

    print etree.tostring(newpom, pretty_print=True)

if __name__ == "__main__":
    main()
