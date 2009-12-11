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
    
    def findmatch(self, product, osname, pool, osversion, hardware, memory, bpp, screenh, screenw):

        print "**** About to find a match ***"
        # Go through the jobs and filter down from most specific job to least        
        jobs = self.db.views.jobs.pendingByJobAttributes(
            startkey=[product, osname, pool, osversion, hardware, memory, bpp, screenh],
            endkey=[product, osname, pool, osversion, hardware, memory, bpp, str(screenh) + '\u9999'],
            limit=1)
        if (len(jobs) is not 0):
            return jobs

        jobs = self.db.views.jobs.pendingByJobAttributes(
            startkey=[product, osname, pool, osversion, hardware, memory, bpp],
            endkey=[product, osname, pool, osversion, hardware, memory, str(bpp) + '\u9999'],
            limit=1)
        if (len(jobs) is not 0):
            return jobs
        
        jobs = self.db.views.jobs.pendingByJobAttributes(
            startkey=[product, osname, pool, osversion, hardware, memory],
            endkey=[product, osname, pool, osversion, hardware, str(memory) + '\u9999'],
            limit=1)
        if (len(jobs) is not 0):
            return jobs
        
        jobs = self.db.views.jobs.pendingByJobAttributes(
            startkey=[product, osname, pool, osversion, hardware],
            endkey=[product, osname, pool, osversion, str(hardware) + '\u9999'],
            limit=1)
        if (len(jobs) is not 0):
            return jobs

        jobs = self.db.views.jobs.pendingByJobAttributes(
            startkey=[product, osname, pool, osversion],
            endkey=[product, osname, pool, str(osversion) + '\u9999'],
            limit=1)
        if (len(jobs) is not 0):
            return jobs

        jobs = self.db.views.jobs.pendingByJobAttributes(
            startkey=[product, osname, pool],
            endkey=[product, osname, str(pool) + '\u9999'],
            limit=1)
        if (len(jobs) is not 0):
            print "++++++ product os and pool match product = " + str(product) + " os = " + str(osname)
            return jobs

        jobs = self.db.views.jobs.pendingByJobAttributes(
            startkey=[product, osname],
            endkey=[product, str(osname) + '\u9999'],
            limit=1)
        if (len(jobs) is not 0):
            print "++++++ product and os match: product = " + str(product) + " os = " + str(osname)
            return jobs

        print "FINDMATCH: returns no job"
        return None

    def get_job(self, client):
        if (client['capabilities'].get('jobtypes')[0] == 'assign'):
            # We have an Agent manager on the line send it an unassigned device
            # Note that if we want Agent managers to respect pools, we will
            # need to query a userdefined pool on the client struct as well
            device = self.db.views.devices.byStatus(key='free', limit=1)
            if (len(device) is 0):
                return None
            else:
                return device[0]
        print "SERVER: getting a job : " + str(client['capabilities'])
        job = self.findmatch(client['capabilities']['device'].get('product'),
                             client['capabilities']['device']['platform'].get('os'),
                             client['capabilities']['device'].get('pool'),
                             client['capabilities']['device']['platform'].get('osversion'),
                             client['capabilities']['device']['platform'].get('hardware'),
                             client['capabilities']['device']['platform'].get('memory'),
                             client['capabilities']['device']['platform'].get('bpp'),
                             client['capabilities']['device']['platform'].get('screenheight'),
                             client['capabilities']['device']['platform'].get('screenwidth'))
        if (not job or len(job) is 0):
            print "SERVER: no job"
            return None
        else:
            return job[0]
     
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
                                   'product':j['product'],
                                   'pool': j['pool'],
                                   'platform': j['platform']})
                    # We have created all jobs for this build, we can now return
                    return jobs
 
                   
        
                                            
        


    
