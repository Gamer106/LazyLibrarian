import platform, subprocess, re, os, urllib2, tarfile, threading

import lazylibrarian
from lazylibrarian import logger, version

import lib.simplejson as simplejson

user = "dobytang"
#branch = "master"
repo="lazylibrarian"

#
#Function to execute GIT commands taking care of error logging etc
def runGit(args):

    git_locations = ['git']
        
    if platform.system().lower() == 'darwin':
        git_locations.append('/usr/local/git/bin/git')
        
    output = err = None
    
    for cur_git in git_locations:
    
        cmd = cur_git+' '+args
    
        try:
            logger.debug('(RunGit)Trying to execute: "' + cmd + '" with shell in ' + lazylibrarian.PROG_DIR)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, cwd=lazylibrarian.PROG_DIR)
            output, err = p.communicate()
            logger.debug('(RunGit)Git output: [%s]' % output)
            
        except OSError:
            logger.debug('(RunGit)Command ' + cmd + ' didn\'t work, couldn\'t find git')
            continue
            
        if 'not found' in output or "not recognized as an internal or external command" in output:
            logger.debug('(RunGit)Unable to find git with command ' + cmd)
            output = None
        elif 'fatal:' in output or err:
            logger.error('(RunGit)Git returned bad info. Are you sure this is a git installation?')
            output = None
        elif output:
            break
            
    return (output, err)
            
#
#function to determine what type of install we are on
# - windows
# - git based
# - deployed source code
def getInstallType():
    
    if version.LAZYLIBRARIAN_VERSION.startswith('win32build'):
        lazylibrarian.INSTALL_TYPE = 'win'
        logger.debug('(getInstallType) Windows install detected')
    
    elif os.path.isdir(os.path.join(lazylibrarian.PROG_DIR, '.git')):
        lazylibrarian.INSTALL_TYPE = 'git'
        logger.debug('(getInstallType) GIT install detected')        
    else:      
        lazylibrarian.INSTALL_TYPE = 'source'
        logger.debug('(getInstallType) Source install detected')

#
#TODO Refactor getVersion to setInstallType
#TODO extract environmental check for windows/git/source to other function
def getVersion():
    version = ''

    if lazylibrarian.INSTALL_TYPE == 'win':
        logger.debug('(getVersion) Windows install - no update available')
        
        # Don't have a way to update exe yet, but don't want to set VERSION to None
        version = 'Windows Install'
        
    elif lazylibrarian.INSTALL_TYPE == 'git':
        output, err = runGit('rev-parse HEAD')
        
        if not output:
            logger.error('Couldn\'t find latest git installed version.')
            version = 'GIT Cannot establish version'
        else:
            cur_commit_hash = output.strip()
        
            if not re.match('^[a-z0-9]+$', cur_commit_hash):
                logger.error('(getVersion) Output doesn\'t look like a hash, not using it')
                version = 'GIT invalid hash return'
            
        version = cur_commit_hash
        
    elif lazylibrarian.INSTALL_TYPE == 'source':
        
        version_file = os.path.join(lazylibrarian.PROG_DIR, 'version.txt')
        
        if not os.path.isfile(version_file):
            version = 'No Version File'
        else:
            fp = open(version_file, 'r')
            current_version = fp.read().strip(' \n\r')
            fp.close()
        
            if current_version:
                version = current_version
            else:
                version =  'No Version set in file'
    
    else:
        logger.error('(getVersion) Install Type not set - cannot get version value')
        version = 'Install type not set'
        
    return version

#
#Returns current branch name of installed version from GIT
#return "NON GIT INSTALL" if INSTALL TYPE is not GIT
def getCurrentGitBranch():
    #Can only work for GIT driven installs, so check install type
    if lazylibrarian.INSTALL_TYPE != 'git':
        logger.debug('Non GIT Install doing check update. Return NON GIT INSTALL')
        return 'NON GIT INSTALL'
    
    # use git rev-parse --abbrev-ref HEAD which returns the name of the current branch
    output, err = runGit('rev-parse --abbrev-ref HEAD')
    
    output = output.strip('\n')
    
    if not output:
        logger.error('failed to return current branch value')
        return 'InvalidBranch'

    logger.debug('Current branch of  repo is [%s] ' % output)
    return output

def checkForUpdates():
    # rename this thread
    threading.currentThread().name = "VERSIONCHECK"
    getInstallType()
    s = getVersion()
    l = checkGithub()


def checkGithub():
    
    
    lazylibrarian.COMMITS_BEHIND = 0
    
    
    #Can only work for GIT driven installs, so check install type
    if lazylibrarian.INSTALL_TYPE != 'git':
        logger.debug('(checkGithub) Non GIT Install doing check update. Return NON GIT INSTALL')
        return 'NON GIT INSTALL'

    #check current branch value of the local git repo as folks may pull from a branch not master
    branch = getCurrentGitBranch()

    # Get the latest commit available from github
    url = 'https://api.github.com/repos/%s/%s/commits/%s' % (user, repo, branch)
    logger.info ('(checkGithub) Retrieving latest version information from github command=[%s]' % url)
    try:
        result = urllib2.urlopen(url).read()
        git = simplejson.JSONDecoder().decode(result)
        lazylibrarian.LATEST_VERSION = git['sha']
        logger.debug('(checkGithub)Latest Version has been set to %s' % lazylibrarian.LATEST_VERSION)
    except:
        logger.warn('(checkGithub) Could not get the latest commit from github')
        lazylibrarian.COMMITS_BEHIND = 0
        lazylibrarian.LATEST_VERSION = 'Not_Available_From_GitHUB'
        return lazylibrarian.LATEST_VERSION
    
    # See how many commits behind we are    
    if lazylibrarian.CURRENT_VERSION:
        logger.info('(checkGithub) Comparing currently installed version with latest github version')
        url = 'https://api.github.com/repos/%s/LazyLibrarian/compare/%s...%s' % (user, lazylibrarian.CURRENT_VERSION, lazylibrarian.LATEST_VERSION)
        logger.debug('(checkGithub) Check for differences between local & repo by [%s]' % url)
        
        try:
            result = urllib2.urlopen(url).read()
            git = simplejson.JSONDecoder().decode(result)
            lazylibrarian.COMMITS_BEHIND = git['total_commits']
            
            logger.info('(checkGithub) GitHub reports as follows Status [%s] - Ahead [%s] - Behind [%s] ' % (git['status'], git['ahead_by'], git['behind_by']))
        except:
            logger.warn('(checkGithub) Could not get commits behind from github. Can happen if you have a local commit not pushed to repo')
            lazylibrarian.COMMITS_BEHIND = 0
            return lazylibrarian.CURRENT_VERSION
            
        if lazylibrarian.COMMITS_BEHIND >= 1:
            logger.info('(checkGithub) New version is available. You are %s commits behind' % lazylibrarian.COMMITS_BEHIND)
        elif lazylibrarian.COMMITS_BEHIND == 0:
            logger.info('(checkGithub) lazylibrarian is up to date')
        elif lazylibrarian.COMMITS_BEHIND == -1:
            logger.info('(checkGithub) You are running an unknown version of lazylibrarian. Run the updater to identify your version')
            
    else:
        logger.info('You are running an unknown version of lazylibrarian. Run the updater to identify your version')
    
    return lazylibrarian.LATEST_VERSION
        
def update():

    
    if lazylibrarian.INSTALL_TYPE == 'win':
        logger.debug('(update) Windows install - no update available')    
        logger.info('(update) Windows .exe updating not supported yet.')
        pass
    

    elif lazylibrarian.INSTALL_TYPE == 'git':

        branch = getCurrentGitBranch()

        output, err = runGit('stash clear')
        output, err = runGit('pull origin ' + branch)
        	
        if not output:
            logger.error('(update) Couldn\'t download latest version')
            
        for line in output.split('\n'):
        
            if 'Already up-to-date.' in line:
                logger.info('(update) No update available, not updating')
                logger.info('(update) Output: ' + str(output))
            elif line.endswith('Aborting.'):
                logger.error('(update) Unable to update from git: '+line)
                logger.info('(update) Output: ' + str(output))
                
    elif  lazylibrarian.INSTALL_TYPE == 'source':

        #As this is a non GIT install, we assume that the comparison is 
        #always to master.
        branch = 'master'
        
        tar_download_url = 'https://github.com/%s/%s/tarball/%s' % (user, repo, branch)
        update_dir = os.path.join(lazylibrarian.PROG_DIR, 'update')
        version_path = os.path.join(lazylibrarian.PROG_DIR, 'version.txt')
        
        try:
            logger.info('(update) Downloading update from: '+tar_download_url)
            data = urllib2.urlopen(tar_download_url)
        except (IOError, URLError):
            logger.error("(update) Unable to retrieve new version from "+tar_download_url+", can't update")
            return
            
        download_name = data.geturl().split('/')[-1]
        
        tar_download_path = os.path.join(lazylibrarian.PROG_DIR, download_name)
        
        # Save tar to disk
        f = open(tar_download_path, 'wb')
        f.write(data.read())
        f.close()
        
        # Extract the tar to update folder
        logger.info('(update) Extracing file' + tar_download_path)
        tar = tarfile.open(tar_download_path)
        tar.extractall(update_dir)
        tar.close()
        
        # Delete the tar.gz
        logger.info('(update) Deleting file' + tar_download_path)
        os.remove(tar_download_path)
        
        # Find update dir name
        update_dir_contents = [x for x in os.listdir(update_dir) if os.path.isdir(os.path.join(update_dir, x))]
        if len(update_dir_contents) != 1:
            logger.error(u"(update) Invalid update data, update failed: "+str(update_dir_contents))
            return
        content_dir = os.path.join(update_dir, update_dir_contents[0])
        
        # walk temp folder and move files to main folder
        for dirname, dirnames, filenames in os.walk(content_dir):
            dirname = dirname[len(content_dir)+1:]
            for curfile in filenames:
                old_path = os.path.join(content_dir, dirname, curfile)
                new_path = os.path.join(lazylibrarian.PROG_DIR, dirname, curfile)
                
                if os.path.isfile(new_path):
                    os.remove(new_path)
                os.renames(old_path, new_path)
                
        # Update version.txt
        try:
            ver_file = open(version_path, 'w')
            ver_file.write(lazylibrarian.LATEST_VERSION)
            ver_file.close()
        except IOError, e:
            logger.error(u"(update) Unable to write current version to version.txt, update not complete: "+ex(e))
            return
    else:
        logger.error("(update) Cannot perform update - Install Type not set")
        return
