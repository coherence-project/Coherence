# $Id: ElementTree.py 2924 2006-11-19 22:24:22Z fredrik $
# can I have some elementtree, please?

try:
    from xml.etree.cElementTree import * # python 2.5
except ImportError:
    try:
        from cElementTree import *
    except ImportError:
        from elementtree.ElementTree import *
