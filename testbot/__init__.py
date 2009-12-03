import os
import sys
import random
import re
from wsgiref.simple_server import make_server
from datetime import datetime

from couchquery import Database
from webenv.applications.file_server import FileServerApplication

this_directory = os.path.abspath(os.path.dirname(__file__))

design_dir = os.path.join(this_directory, 'design')
static_dir = os.path.join(this_directory, 'static')
clients_design_dir = os.path.join(design_dir, 'clients')
jobs_design_dir = os.path.join(design_dir, 'jobs')
builds_design_dir = os.path.join(design_dir, 'builds')
mozilla_design_dir = os.path.join(design_dir, 'mozilla')
devices_design_dir = os.path.join(design_dir, 'devices')
jobmap_design_dir = os.path.join(design_dir, 'jobmap')

def create_job(db, job):
    job['type'] = 'job'
    job['creationdt'] = datetime.now().isoformat()
    job['status'] = 'pending'
    db.create(job)

def sync(db):
    db.sync_design_doc('clients', clients_design_dir)
    db.sync_design_doc('jobs', jobs_design_dir)
    db.sync_design_doc('builds', builds_design_dir)
    db.sync_design_doc('mozilla', mozilla_design_dir)
    db.sync_design_doc('devices',devices_design_dir)
    db.sync_design_doc('jobmap',jobmap_design_dir)

def cli():
    if not sys.argv[-1].startswith('http'):
        dburi = 'http://localhost:5984/testbot'
    else:
        dburi = sys.argv[-1]
    
    db = Database(dburi)
    sync(db)
    print "Using CouchDB @ "+dburi
    from testbot.server import TestBotApplication
    application = TestBotApplication(db, MozillaManager())
    application.add_resource('static', FileServerApplication(static_dir))
    httpd = make_server('', 8888, application)
    print "Serving on http://localhost:8888/"
    httpd.serve_forever()
    
class TestBotManager(object):
    pass    

class MozillaManager(object):
    """Logic for handling Mozilla's builds and tests"""
    
    all_mobile_testtypes = [
        # Unittests
        'mochitest', 'mochitest-chrome', 'browser-chrome', 'reftest', 'crashtest', 
        'js-reftest', 'xpcshell',
        # Talos
        'talos-ts', 'talos-ts_cold', 'talos-ts_places_generated_max', 
        'talos-ts_places_generated_min', 'talos-ts_places_generated_med', 
        'talos-tp', 'talos-tp4', 'talos-tp_js', 'talos-tdhtml', 'talos-tgfx', 
        'talos-tsvg', 'talos-twinopen', 'talos-tjss', 'talos-tsspider', 
        'talos-tpan', 'talos-tzoom',
        ]
    
    def get_job(self, client):
        if client['capabilities']['platform'].get('os.sysname', None) == 'Linux':
            if client['capabilities']['platform'].get('os.linux.distrobution',[None])[0] == 'CentOS':
                # Desktop linux
                supported_jobtypes = client['jobtypes']
                while len(supported_jobtypes) is not 0:
                    jtype = random.sample(supported_jobtypes, 1)[0]
                    result = self.db.views.mozilla.desktopBuilds(
                        startkey=['Linux', jtype, {}], endkey=['Linux', jtype, None], 
                        descending=True, limit=1)
                    if len(result) is not 0:
                        return result[0]
                    supported_jobtypes.remove(jtype)
                # No jobs were found
        
                return None
    
    def new_build(self, build):
        jobs = []
        # Get the mapping of our job table
        jobmaprows = self.db.views.jobmap.byBuild()        
        for u in build['uris']:
            for j in jobmaprows:
                if re.search(j['build'], u):
                    packageURI = u
                    # get test package
                    for t in build['uris']:
                        if re.search(j['testpackage'], t):
                          testURI = t
                          break
                    # Create the jobs for this build
                    for jobtype in j['jobtypes']:
                      jobs.append({'build': j['build'],
                                   'jobtype': jobtype,
                                   'package_uri': packageURI,
                                   'tests_uri': testURI,
                                   'product':j['build'],
                                   'pool': j['pool'],
                                   'platform': j['platform']})
                    # We have created all jobs for this build, we can now return
                    print "This is jobs created: " + str(jobs)
                    return jobs
 
                   
        
                                            
        


    
