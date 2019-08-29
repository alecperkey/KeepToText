#!/usr/bin/env python3

from __future__ import print_function
import sys, glob, os, shutil, zipfile, time, codecs, re, argparse
from zipfile import ZipFile
from dateutil.parser import parse, parserinfo
from html.parser import HTMLParser

class InvalidEncoding(Exception):
    def __init__(self, inner):
        Exception.__init__(self)
        self.inner = str(inner)

def noteToText(outputDir, note):
    #print('Note "{}" has {} characters, modified on {}.'.format(
    #    note.new_name(), len(note.text), note.ctime))
    if len(note.text) == 0:
      print('Note named "{}" has no characters'.format(note.new_name()))
    outfname = os.path.join(outputDir, note.new_name())
    try:
        with codecs.open(outfname, "w", outputEncoding) as outf:
            outf.write(note.text)
        mod_time = time.mktime(note.ctime.timetuple())
        os.utime(outfname, (mod_time, mod_time))
    except UnicodeEncodeError as ex:
        print("Skipping file " + inputPath + ": " + str(ex))
    except LookupError as ex:
        raise InvalidEncoding(ex)

def tryUntilDone(action, check):
    ex = None
    i = 1
    while True:
        try:
            if check(): return
        except Exception as e:
            ex = e
        if i == 20: break
        try:
            action()
        except Exception as e:
            ex = e
        time.sleep(1)
        i += 1
    sys.exit(ex if ex != None else "Failed")

def try_rmtree(dir):
    if os.path.isdir(dir):
      print("Removing {0}".format(dir))

    def act(): shutil.rmtree(dir)
    def check(): return not os.path.isdir(dir)
    tryUntilDone(act, check)

def try_mkdir(dir):
    def act(): os.mkdir(dir)
    def check(): return os.path.isdir(dir)
    tryUntilDone(act, check)

htmlExt = re.compile(r"\.html$", re.I)

class Note:
    def __init__(self, path, heading, text):
        self.path = path
        self.ctime = parse(heading, parserinfo(dayfirst=True))
        self.text = text

    def new_name(self):
        return os.path.basename(self.path).replace(".html", ".md")


def extractNoteFromHtmlFile(inputPath):
    """
    Extracts the note heading (containing the ctime), text, and labels from
    an exported Keep HTML file
    """

    with codecs.open(inputPath, 'r', 'utf-8') as myfile:
        data = myfile.read()

    from lxml import etree
    tree = etree.HTML(data)

    # Prepend \n to all of the <br> tags to preserve newlines.
    for br in tree.xpath("*//br"):
        br.tail = "\n" + br.tail if br.tail else "\n"

    heading = tree.xpath("//div[@class='heading']/text()")[0].strip()
    text = ''.join(tree.xpath("//div[@class='content']/text()"))

    if not text:
        # It might be a list. Try to parse out the list items and convert into a
        # markdown-style list.
        items = []
        for li in tree.xpath("*//li/span[@class='text']/text()"):
            items.append('- ' + li)
        text = '\n'.join(items)


    return Note(inputPath, heading, text)

def processHtmlFiles(inputDir):
    "Iterates over Keep HTML files to extract relevant notes data"

    print("Processing HTML files in {}".format(inputDir))

    notes = []
    for path in glob.glob(os.path.join(inputDir, "*.html")):
        try:
            note = extractNoteFromHtmlFile(path)
            notes.append(note)
        except IndexError: pass

    return notes

def getHtmlDir(takeoutDir):
    "Returns first subdirectory beneath takeoutDir which contains .html files"
    dirs = [os.path.join(takeoutDir, s) for s in os.listdir(takeoutDir)]
    for dir in dirs:
        if not os.path.isdir(dir): continue
        htmlFiles = [f for f in os.listdir(dir) if htmlExt.search(f)]
        if len(htmlFiles) > 0: return dir

def keepZipToOutput(zipFileName):
    zipFileDir = os.path.dirname(zipFileName)
    takeoutDir = os.path.join(zipFileDir, "Takeout")
    try_rmtree(takeoutDir)
    if os.path.isfile(zipFileName):
        print("Extracting {0} ...".format(zipFileName))

    try:
        with ZipFile(zipFileName) as zipFile:
            zipFile.extractall(zipFileDir)
    except (IOError, zipfile.BadZipfile) as e:
        sys.exit(e)

    htmlDir = getHtmlDir(takeoutDir)
    if htmlDir is None: sys.exit("No Keep directory found")
    print("Keep dir: " + htmlDir)

    notes = processHtmlFiles(inputDir=htmlDir)

    outputDir = os.path.join(zipFileDir, "Text")

    # Convert each note into a plaintext file with the parsed out creation time.
    try_mkdir(outputDir)
    for note in notes:
        noteToText(outputDir, note)

def setOutputEncoding():
    global outputEncoding
    outputEncoding = args.encoding
    if outputEncoding is not None: return
    if args.system_encoding: outputEncoding = sys.stdin.encoding
    if outputEncoding is not None: return
    outputEncoding = "utf-8"

def getArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("zipFile")
    parser.add_argument("--encoding",
        help="character encoding of output")
    parser.add_argument("--system-encoding", action="store_true",
        help="use the system encoding for the output")
    global args
    args = parser.parse_args()

def main():
    getArgs()
    setOutputEncoding()

    try:
        keepZipToOutput(args.zipFile)
    except WindowsError as ex:
        sys.exit(ex)
    except InvalidEncoding as ex:
        sys.exit(ex.inner)

if __name__ == "__main__":
    main()

