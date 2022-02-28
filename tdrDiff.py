#!/usr/bin/env python3

""" Script to generate a latexdiff PDF of two different revisions of a tdr-style document.

    On lxplus you need a late-ish version of git and Python 3.
    Try "scl enable rh-git29 enable bash", and the same for rh-python36.

    """



# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
import logging
import shutil
import subprocess
from pathlib import Path
import os
import tempfile
import argparse
import time, datetime, pytz, datetime
import sys
import urllib








# %%


class tdrDiff(object):
    """
    tdrDiff: class to do the work of fetching two different versions of the same GitLab tdr project, produce full TeX files, run latexdiff on them, and produce a PDF output file.

    Requires that you have installed versions of git, pdflatex, latexdiff, and latexmk

    """

    accessString = {'http': 'https://gitlab.cern.ch/tdr/', 'ssh': 'ssh://git@gitlab.cern.ch:7999/tdr/', 'krb': 'https://:@gitlab.cern.ch:8443/tdr/'}

    def __init__(self, docTag, docPath='papers',  revDiff='HEAD~1', verbosity=0, accessType='ssh', outfile=None, revBase='HEAD', logfile=None, plotsFromRevBase=False):
        """
        :arg docTag: the document name, eg, HIG-19-001
        :arg docType: the document type, note or paper:
        :arg revDiff: the other revision 
        :arg verbosity: logging verbosity 0:2
        :arg accessType: ssh/http/krb or explicit URL
        :arg outfile: file name for output PDF
        :arg revBase: the base revision
        :arg logFile: optional file to store log output
        """

        self._t0  = time.time()
        self._docTag = docTag
        self._revBase = revBase
        self._revDiff = revDiff
        self._plotsFromRevBase = plotsFromRevBase
        if accessType in tdrDiff.accessString.keys():
            self._url = tdrDiff.accessString[accessType]+docPath+'/'+docTag
        else:
            if urllib.parse.urlparse(accessType):
                self._url = accessType
        self._outfile = outfile
        v = {0:logging.WARNING, 1:logging.INFO, 2:logging.DEBUG}
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(v[min([2,verbosity])]) # clamp at the maximum level
        if (verbosity>2): # if high verbosity, echo subprocess output
            self._procout = None
        else:
            self._procout = subprocess.DEVNULL
        self._logger.debug('Creating tdrDiff instance; Starting logging')
        self._tdrExe = (Path(__file__).parent / '../utils/tdr').resolve(True) # pick up local tdr
        self._startDir = Path.cwd()
        if logfile:
            logname = Path.home()/logfile
            self._flogger = logging.FileHandler(filename=logname) # default for logging is to append
            self._flogger.setLevel(logging.DEBUG)
            self._logger.addHandler(self._flogger)
        self._logger.debug('#### Start: %s. Target: %s', datetime.datetime.utcnow().replace(tzinfo=pytz.UTC).strftime('%Y-%m-%d %H:%M %Z'), docTag)
        self.versionCheck()

    def versionCheck(self):
        """ find the locations of the required external programs and do sanity checks

            :output program locations in self:
        """
        # git version
        git = shutil.which('git')
        proc = subprocess.run(['git', '--version'], check=True, stdout=subprocess.PIPE)
        if proc:
            (major, minor, *_) = (((proc.stdout.decode('utf-8')).split(' '))[2]).split('.')
            if int(major) < 2 or (int(major)==2 and int(minor) <9 ):
                print('Git version (%s.%s) is too low. Need at least 2.9'%(major, minor))
                exit()
            else:
                self._git = Path(git)
        
        # python version
        (major, minor, *_) = sys.version_info
        if int(major) <3 or int(minor)<6:
            print('Python version (%s.%s) is too low. Need at least 3.6'%(major, minor))

        # latexmk and latexdiff
        lmk = shutil.which('latexmk')
        if not lmk:
            # try looking in standard lxplus location
            cvmfs = Path('/cvmfs/cms.cern.ch/external/tex/texlive/2017/bin/x86_64-linux/')
            lmk = cvmfs / 'latexmk'
            latexdiff = cvmfs / 'latexdiff'
            if not (lmk.exists() and latexdiff.exists()):
                print('Could not find latexdiff and latexmk')
                exit()
        else:
            lmk = Path(lmk)
            # look for local for latexdiff as well
            latexdiff = Path(shutil.which('latexdiff'))
            if not (lmk.exists() and latexdiff.exists()):
                print('Could not find latexdiff and latexmk')
                exit()
        self._lmk = lmk
        self._latexdiff = latexdiff
 
    def goToWorkDir(self, workDir):
        """ Use a temporary area to avoid overwriting the current checked out repo
        :param workDir: the directory to work in 
        """
        os.chdir(workDir) # starting work area
        self._logger.info("Temporarily working in %s", workDir)
        self._logger.info("Cloning...")
        # clone HEAD
        subprocess.run([str(self._git), 'clone','--recursive', self._url], check=True, stdout=self._procout, stderr=self._procout)
        print("Checked out %s" % self._url)
        os.chdir(self._docTag)


    def differ(self):
        """ Do the work. All arguments taken from class 
        
        :return: copies the output PDF file to self._outfile
        """
        if not os.path.exists("build_tdrDiff"): os.makedirs("build_tdrDiff")
        workDir = Path(os.path.abspath("build_tdrDiff")) # this is a "permanent" temporary directory. It is not automatically deleted after use.
        revBaseOriginal = self._revBase
        revDiffOriginal = self._revDiff
        revBaseHash = subprocess.run(["git", "rev-parse", self._revBase], stdout=subprocess.PIPE).stdout.decode("utf-8").strip() if self._revBase != "." else "current"
        revDiffHash = subprocess.run(["git", "rev-parse", self._revDiff], stdout=subprocess.PIPE).stdout.decode("utf-8").strip()
        print("#### Build parameters ####")
        print("revBase: "+str(self._revBase)+" hash("+revBaseHash+")")
        print("revDiff: "+str(self._revDiff)+" hash("+revDiffHash+")")
        print("workDir: "+str(workDir))
        print("#### Build parameters ####\n")
        # Convert revision to hash tag
        self._revBase = revBaseHash
        self._revDiff = revDiffHash

        # '.' is current working version
        if (self._revBase != 'current'):
            # Clone if .git does not exist
            if not os.path.exists("build_tdrDiff/"+self._docTag+"/.git"):
              self.goToWorkDir(workDir)
            else:
              os.chdir(workDir) # starting work area
              os.chdir(self._docTag)

            # optionally change from HEAD to a different base commit (revBase)
            if self._revBase != 'HEAD' and self._revBase != 'current':
                subprocess.run([str(self._git), 'checkout', self._revBase], check=True, stdout=self._procout, stderr=self._procout)

            print("Checked out revBase: %s" % self._revBase)


        # build the export directory for the revBase
        print("Building export directory for revBase: %s" % self._revBase)
        export0 = workDir/('export_'+self._revBase) # move export directory to new work area
        if not os.path.exists(export0) or self._revBase == 'current': 
          try:
              subprocess.run(['perl', str(self._tdrExe), '--export', '--admin=nolineno', 'b', self._docTag], check=True, stdout=self._procout)
          except subprocess.CalledProcessError as e:
              self._logger.exception('Problems running rev %s. Full error message follows.',self._revBase)
              print(e.output)
          # Move revBase to folder
          os.rename('export',export0)
          print('Output of revBase: %s moved to %s\n' % (self._revBase, Path(export0)))
        else:
          print('Export %s exists. Do not need to rebuild.\n' % (Path(export0)))

        # '.' is current working version
        if (self._revBase == 'current'):
            # Clone if .git does not exist
            if not os.path.exists("build_tdrDiff/"+self._docTag+"/.git"):
              self.goToWorkDir(workDir)
            else:
              os.chdir(workDir) # starting work area
              os.chdir(self._docTag)

        # now get diff revision to differ against
        subprocess.run([str(self._git), 'checkout', self._revDiff], check=True, stdout=self._procout, stderr=self._procout)
        print("Checked out revDiff: %s" % self._revDiff)

        # build document
        print("Building export directory for revDiff: %s" % self._revDiff)
        export1 = workDir/('export_'+self._revDiff)
        if not os.path.exists(export1):
          try:
              subprocess.run(['perl', str(self._tdrExe), '--export', '--admin=nolineno', 'b', self._docTag], check=True, stdout=self._procout)  
          except subprocess.CalledProcessError as e:
              self._logger.exception('Problems running rev %s. Full error message follows.',self._revDiff)
              print(e.output)
          # Move revDiff to folder
          os.rename('export',export1)
          print('Output of revDiff: %s moved to %s\n' % (self._revDiff, Path(export1)))
        else:
          print('Export %s exists. Do not need to rebuild.\n' % (Path(export1)))

        # Choose where plots should be from
        if self._plotsFromRevBase: os.chdir(export0) # need to work in directory with all TeX includes. Go to revBase
        else: os.chdir(export1) # need to work in directory with all TeX includes. Go to revDiff

        # Generate the diference document between the two revisions
        print('Working in %s\n' % Path.cwd())
        docName = self._docTag + '_temp.tex'
        diffile = Path(self._docTag +'_diff.tex') # the TeX file of differences
        print("Running latexdiff: "+" ".join([str(self._latexdiff), '--verbose', '--flatten', '--allow-spaces', str(export1/docName), str(export0/docName)]))
        print("Output latexdiff file: "+str(diffile.absolute()))
        with open(diffile, mode='w') as out:
            try:
                subprocess.run([str(self._latexdiff), '--verbose', '--flatten', '--allow-spaces', str(export1/docName), str(export0/docName)], stdout=out, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                self._logger.exception('Problems running latexdiff. Full error message follows.')
                print(e.output)

        # and convert the difference TeX to PDF        
        print("Running latexmk: "+" ".join([str(self._lmk), '-pdf', '-f', '-latexoption="-interaction=batchmode"', str(diffile.absolute())]))
        try:
            subprocess.run([str(self._lmk), '-pdf', '-f', '-latexoption="-interaction=batchmode"', str(diffile.absolute())], check=True, stdout=self._procout, stderr=subprocess.PIPE) # batchmode runs over errors, -f forces latexmk to proceed
        except subprocess.CalledProcessError as e:
            self._logger.exception('Problems running latexmk. Full error message follows.')
            print(e.output)
            print('[Note] Errors can be ignored, in the case there are new plots.')
            print('[Note] revBase plots can be used instead of revDiff plots with --plotsFromRevBase option.')
            print('Run again with verbosity > 2 to get error output from latexmk.')

        # finally, copy the PDF back to the starting location
        difpdf =  Path.cwd() / Path(self._docTag +'_diff.pdf') 
        os.chdir(self._startDir)
        if difpdf.exists():
            if self._outfile:
                dest = self._outfile
            else:
                dest = self._startDir    
            newdif = shutil.copy(difpdf, dest)
            #self._logger.info("Copied latexdiff output to %s", newdif)
            print("Copied latexdiff output to %s"%newdif)
        else:
            self._logger.warn('PDF file not created')
        
        # Restore revision to original
        self._revBase = revBaseOriginal
        self._revDiff = revDiffOriginal

        # Done
        self._logger.debug('#### Finish: %s. Target: %s',datetime.datetime.utcnow().replace(tzinfo=pytz.UTC).strftime('%Y-%m-%d %H:%M %Z'),self._docTag)



# %%
def main(argv):

    parser = argparse.ArgumentParser(description='Generate latexdiffs for a tdr document. Requires installed versions of git, latexdiff, and latexmk.')
    parser.add_argument('-v', '--verbosity', action='count', dest='verbose', default=False,
                        help='trace script execution: default is WARN, using -v will increase through INFO, DEBUG. -v -v -v gives output from called programs.')
    parser.add_argument(  '--revBase', action='store', dest='revBase', default='HEAD', 
                        help='base revision for differ. Default: HEAD. If revBase is ".", the current working directory is used instead of checking out a version.')
    parser.add_argument( '--revDiff', action='store', dest='revDiff', default="HEAD~1", 
                        help='revision for comparison. Defalut: HEAD~1. Accepts SHAs')
    parser.add_argument( '--plotsFromRevBase', action='store_true', dest='plotsFromRevBase',
                        help='Use plots from revBase instead of revDiff')
    parser.add_argument( '-p', '--path', action='store', dest='docPath', default='notes', choices=('notes','papers'),
                        help='path below tdr to the document: an, dn, etc. and PAS are all under notes. Default: notes')
    parser.add_argument(  '-l', '--logfile', action='store', dest='logfile', nargs='?', const='differLog.txt',
                        help='file name for diagnostic logger output. Default: differLog.txt')
    parser.add_argument(  '--outfile', action='store', dest='outfile',
                        help='path for output PDF file; Default: <tag>_diff in cwd')
    parser.add_argument(  '--accessType', action='store', dest='accessType', default='ssh',
                        help='git access type. It is assumed that the correct keys are already established [{}, {}, {}, arbitrary (full URL)]. Default: SSH'.format(*tdrDiff.accessString.keys()) )
    parser.add_argument( 'tag', 
                        help='the document tag, eg, HIG-18-001')


    opts = parser.parse_args()

    if opts.verbose:
        print('\tVerbosity = {}\n\n'.format(opts.verbose))

    d = tdrDiff(opts.tag, opts.docPath, opts.revDiff, opts.verbose, opts.accessType, opts.outfile, opts.revBase, opts.logfile, opts.plotsFromRevBase)
    d.differ()




if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
