#!/usr/bin/env python3

################################################################################
# ripple-dev-portal doc parser
#
# Generate the html for all the Ripple Dev  Portal files from a template
# Optionally pre-compile them to HTML (using pandoc & a custom filter)
################################################################################

from jinja2 import Environment, FileSystemLoader
import os, sys, re
import json
import argparse

##Necessary for pandoc, prince
import subprocess

#Python markdown works instead of pandoc
from markdown import markdown
from bs4 import BeautifulSoup

#Watchdog stuff
import time#, logging
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler


DOC_TEMPLATE_FILE = "template-doc.html"
PDF_TEMPLATE_FILE = "template-forpdf.html"
PAGE_MANIFEST_FILE = "pages.json"
BUILD_PATH = ".."
CONTENT_PATH = "../content"
BUTTONIZE_FILTER = "buttonize.py"
PRINCE_PAGE_MANIFEST_FILE = "/tmp/devportal-pages.txt"

def parse_markdown(md):
    ## Python markdown requires markdown="1" on HTML block elements
    ##     that contain markdown. AND there's a bug where if you use
    ##     markdown.extensions.extra, it replaces code fences in HTML
    ##     block elements with garbled text
    def add_markdown_class(m):
        if m.group(0).find("markdown=") == -1:
            return m.group(1) + ' markdown="1">'
        else:
            return m.group(0)
    
    md = re.sub("(<div[^>]*)>", add_markdown_class, md)
    
    #the actual markdown parsing is the easy part
    html = markdown(md, extensions=["markdown.extensions.extra", "markdown.extensions.toc"])
    
    #replace underscores with dashes in h1,h2,etc. for Flatdoc compatibility
    soup = BeautifulSoup(html, "html.parser")
    headers = soup.find_all(name=re.compile("h[0-9]"), id=True)
    for h in headers:
        if "_" in h["id"]:
            h["id"] = h["id"].replace("_","-")
    
    html2 = soup.prettify()
    return html2
    
def get_pages():
    print("reading page manifest...")
    with open(PAGE_MANIFEST_FILE) as f:
        pages = json.load(f)
    print("done")
    return pages

def render_pages(precompiled, pdf=False):
    pages = get_pages()
    
#    if pdf:
#        precompiled = True#Prince probably won't work otherwise
#        with open(PRINCE_PAGE_MANIFEST_FILE,"w") as f:
#            for page in pages:
#                if "md" in page:
#                    f.write(page["html"])
#                    f.write("\n\n")
    
    env = Environment(loader=FileSystemLoader(os.path.curdir))
    env.lstrip_blocks = True
    env.trim_blocks = True

    for currentpage in pages:
    
        if "md" in currentpage:
            # Documentation file
    
            print("reading template file...")
            
#            with open(DOC_TEMPLATE_FILE) as f:
#                template_text = f.read()
#            doc_template = Template(template_text)
            doc_template = env.get_template(DOC_TEMPLATE_FILE)
            if pdf:
                doc_template = env.get_template(PDF_TEMPLATE_FILE)
            print("done")
            
    
            if precompiled:
                filein = os.path.join(CONTENT_PATH, currentpage["md"])
                print("parsing markdown for", currentpage)
                ## New markdown module way
                with open(filein) as f:
                    s = f.read()
                    doc_html = parse_markdown(s)
                
#                ## Old Pandoc way
#                args = ['pandoc', filein, '-F', BUTTONIZE_FILTER, '-t', 'html']
#                print("compiling: running ", " ".join(args),"...")
#                doc_html = subprocess.check_output(args, universal_newlines=True)
                print("done")
                
                print("rendering page",currentpage,"...")
                out_html = doc_template.render(currentpage=currentpage, pages=pages, 
                                               content=doc_html, precompiled=precompiled)
                print("done")
            
            else:
                print("compiling skipped")
                
                print("rendering page",currentpage,"...")
                out_html = doc_template.render(currentpage=currentpage, pages=pages, 
                                               content="", precompiled=precompiled)
                print("done")
        
        else:
            # Not a documentation page
            print("reading template file...")
#            with open(currentpage["template"]) as f:
#                template_text = f.read()
#            template = Template(template_text)
            template = env.get_template(currentpage["template"])
            print("done")
            
            
            print("rendering page",currentpage,"...")
            out_html = template.render(currentpage=currentpage, pages=pages)
            print("done")
            
        
        fileout = os.path.join(BUILD_PATH, currentpage["html"])
        if (not os.path.isdir(BUILD_PATH)):
            print("creating build folder",BUILD_PATH)
            os.makedirs(BUILD_PATH)
        with open(fileout, "w") as f:
            print("writing to file:",fileout,"...")
            f.write(out_html)
            print("done")


def watch(pre_parse, pdf):
    path = ".."
    class UpdaterHandler(PatternMatchingEventHandler):
        def on_any_event(self, event):
            print("got event!")
            if pdf:
                make_pdf(pdf)
            render_pages(pre_parse, pdf)
    
    patterns = ["*tool/pages.json","*tool/template-*.html"]
    if pre_parse:
        #md only prompts HTML change if pre-parsed
        patterns.append("*content/*.md",)
    event_handler = UpdaterHandler(patterns=patterns)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    #The above starts an observing thread, so the main thread can just wait
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def make_pdf(outfile):
    print("rendering PDF-able versions of pages...")
    render_pages(True, outfile)
    print("done")
    
    args = ['prince', '-o', outfile, "../index.html"]
    pages = get_pages()
    args += ["../"+p["html"] for p in pages if "md" in p]
    print("generating PDF: running ", " ".join(args),"...")
    prince_resp = subprocess.check_output(args, universal_newlines=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate static site from markdown and templates.')
    parser.add_argument("-p", "--pre_parse", action="store_true",
                       help="Parse markdown; otherwise, use Flatdoc")
    parser.add_argument("-w","--watch", action="store_true",
                       help="Watch for changes and re-generate the files. This runs until force-quit.")
    parser.add_argument("--pdf", type=str, help="Generate a PDF, too. Requires Prince.")
    args = parser.parse_args()
    
    if args.pdf:
        if args.pdf[-4:] != ".pdf":
            exit("PDF filename must end in .pdf")
        make_pdf(args.pdf)
    #Not an accident that we go on to re-gen files in non-PDF format
    
    if args.watch:
        watch(args.pre_parse, args.pdf)
    else:
        render_pages(args.pre_parse)
    
