# -*- coding: utf-8 -*-
"""
    pyrseas.augment.function
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This module defines two classes: CfgFunction derived from
    DbAugment and CfgFunctionDict derived from DbAugmentDict.
"""
from pyrseas.augment import DbAugmentDict, DbAugment
from pyrseas.dbobject.function import Function


class CfgFunctionSource(DbAugment):
    "A configuration function source or part thereof"
    pass


class CfgFunctionSegment(CfgFunctionSource):
    "A repeatable segment used in a function source template"

    def replace(self, strans_tbl, mtrans_tbl):
        """Replace patterns in repeatable segments

        :param strans_tbl: single-item translation table
        :param mtrans_tbl: multiple-item translation table
        :return: translated source segment
        """
        join = ', '
        if hasattr(self, 'join'):
            join = self.join
        src = self.source
        for (pat, repl) in strans_tbl:
            if '{{' in src:
                src = src.replace(pat, repl)

        beg = 0
        mseglist = []
        while True:
            beg = src.find('{{', beg)
            if beg < 0:
                break
            beg += 2
            end = src[beg:].find('}}')
            seg = src[beg:beg + end]
            beg = beg + end
            if seg in mtrans_tbl:
                if len(mtrans_tbl[seg]) == 1:
                    src = src.replace('{{%s}}' % seg, mtrans_tbl[seg][0])
                else:
                    if seg not in mseglist:
                        mseglist.append(seg)

        segs = []
        if len(mseglist):
            for (i, col) in enumerate(mtrans_tbl[mseglist[0]]):
                srcseg = src
                for seg in mseglist:
                    srcseg = srcseg.replace('{{%s}}' % seg, mtrans_tbl[seg][i])
                segs.append(srcseg)
        else:
            segs = [src]

        return join.join(segs)


class CfgFunctionTemplate(CfgFunctionSource):
    "A configuration function source template"

    pass


class CfgFunctionSourceDict(DbAugmentDict):

    cls = CfgFunctionSource

    def __init__(self, cfg_templates, cfg_segments):
        for seg in cfg_segments:
            src = cfg_segments[seg]
            dct = {'source': src[0]}
            if len(src) == 2:
                dct.update(join=src[1])
            self[seg] = CfgFunctionSegment(name=seg, **dct)
        for templ in cfg_templates:
            src = cfg_templates[templ]
            dct = {'source': src}
            self[templ] = CfgFunctionTemplate(name=templ, **dct)


class CfgFunction(DbAugment):
    "A configuration function definition"

    keylist = ['name', 'arguments']

    def adjust_name(self, trans_tbl):
        """Replace function configuration name by actual name

        :param trans_tbl: translation table
        """
        name = self.name
        if '{{' in name:
            for (pat, repl) in trans_tbl:
                if pat in name:
                    name = name.replace(pat, repl)
                    break
        return name

    def apply(self, schema, trans_tbl, augdb):
        """Add a function to a given schema.

        :param schema: name of the schema in which to create the function
        :param trans_tbl: translation table
        :param augdb: augmenter dictionaries
        """
        newfunc = Function(schema=schema, **self.__dict__)
        newfunc.volatility = 'v'
        src = newfunc.source
        if '{{' in src and '}}' in src:
            pref = src.find('{{')
            prefix = src[:pref]
            suf = src.find('}}')
            suffix = src[suf + 2:]
            tmplkey = src[pref + 2:suf]
            if tmplkey not in augdb.funcsrcs:
                raise KeyError("Function template '%s' not found" % tmplkey)
            newfunc.source = prefix + augdb.funcsrcs[tmplkey].source + suffix

        if isinstance(trans_tbl, dict) and 'single' in trans_tbl:
            strans_tbl = trans_tbl['single']
            mtrans_tbl = trans_tbl['multi']
        else:
            strans_tbl = trans_tbl
            mtrans_tbl = []
        src = newfunc.source
        beg = 0
        for i in range(src.count('{{')):
            beg = src.find('{{', beg) + 2
            end = src[beg:].find('}}')
            seg = src[beg:beg + end]
            if seg in augdb.funcsrcs:
                src = src.replace('{{%s}}' % seg, augdb.funcsrcs[seg].replace(
                    strans_tbl, mtrans_tbl))
            if seg in mtrans_tbl:
                src = src.replace('{{%s}}' % seg, mtrans_tbl[seg][0])

        newfunc.source = src
        for (pat, repl) in strans_tbl:
            if '{{' in newfunc.source:
                newfunc.source = newfunc.source.replace(pat, repl)
            if '{{' in newfunc.name:
                newfunc.name = newfunc.name.replace(pat, repl)
            if '{{' in newfunc.description:
                newfunc.description = newfunc.description.replace(pat, repl)
        return newfunc


class CfgFunctionDict(DbAugmentDict):
    "The collection of configuration functions"

    cls = CfgFunction

    def __init__(self, config):
        for func in config:
            fncdict = config[func]
            paren = func.find('(')
            (fnc, args) = (func[:paren], func[paren + 1:-1])
            fncname = fnc
            dct = fncdict.copy()
            if 'name' in dct:
                fncname = dct['name']
                del dct['name']
            self[fnc] = CfgFunction(name=fncname, arguments=args, **dct)

    def from_map(self, infuncs):
        """Initialize the dictionary of functions by converting the input list

        :param infuncs: YAML list defining the functions
        """
        for func in infuncs:
            paren = func.find('(')
            (fnc, args) = (func[:paren], func[paren + 1:-1])
            if fnc in self:
                cfnc = self[fnc]
            else:
                self[fnc] = cfnc = CfgFunction(name=fnc, arguments=args)
            for attr, val in list(infuncs[func].items()):
                setattr(cfnc, attr, val)