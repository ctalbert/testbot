import os
from datetime import datetime
try:
    import json
except:
    import simplejson as json

from webenv.rest import RestApplication
from webenv import Response, HtmlResponse, Response201, Response404
from mako.lookup import TemplateLookup

this_directory = os.path.abspath(os.path.dirname(__file__))

lookup = TemplateLookup(directories=[os.path.join(this_directory, 'templates')], encoding_errors='ignore', input_encoding='utf-8', output_encoding='utf-8')

class MakoResponse(HtmlResponse):
    def __init__(self, name, **kwargs):
        template = lookup.get_template(name+'.mko')
        kwargs['json'] = json
        self.body = template.render_unicode(**kwargs).encode('utf-8', 'replace')
        self.headers = []
        
class JSONResponse(Response):
    content_type = 'application/json'
    def __init__(self, obj):
        self.body = json.dumps(obj)
        self.headers = []

class Response204(Response):
    status = '204 Not Content'

class TestBotApplication(RestApplication):
    def __init__(self, db, manager):
        RestApplication.__init__(self)
        self.db = db
        self.manager = manager
        self.add_resource("api", TestBotAPI(db, manager))
        
    def GET(self, request, collection=None, resource=None):
        if collection is None:
            return # Index
        if collection == 'clients':
            if resource is None:
                pass # Client Index
            client = self.db.get(resource)
            if client.type != 'client':
                return Response404()
            return JSONResponse(client)
        if collection == 'jobs':
            if resource is None:
                pass # Jobs Index
            job = self.db.get(resource)
            if job.type != 'job':
                return Response404()
            # Placeholder response until we write a template
            return JSONResponse(job)
        if collection == 'builds':
            if resource is None:
                limit = request.query.get('limit', 10)
                latest_builds = self.db.views.builds.byTimestamp(limit=10, descending=True)
                print len(latest_builds)
                latest_jobs = self.db.views.jobs.byBuild(keys=[b['_id'] for b in latest_builds])
                for build in latest_builds:
                    build['jobs'] = latest_jobs[build['_id']]
                return MakoResponse('builds', builds=latest_builds)
            build = self.db.get(resource)
            if build.type != 'build':
                return Response404()
            # Placeholder response until we write a template
            return JSONResponse(build)

class TestBotAPI(RestApplication):
    def __init__(self, db, manager):
        RestApplication.__init__(self)
        self.db = db
        self.manager = manager
        self.manager.db = db
        # TODO: This will become a user centric configuration issue, and we will
        # take this code out, but right now I need a way to easily seed an
        # empty db, so this is it.
        self.configureJobMapping()
    
    def configureJobMapping(self):
        # Make us a mapping for default maemo fennec job
        jobmap = {'type': 'jobmap',
                  'build':'.*fennec.*linux-gnueabi-arm\.tar\.bz2',
                  'product': 'fennec',
                  'testpackage':'xulrunner.*linux-gnueabi-arm\.tests\.tar\.bz2',
                  'platform': {'os.sysname': 'maemo',
                               'os.version': '',
                               'hardware': '',
                               'memory': '',
                               'bpp':'',
                               'screenh':'',
                               'screenw':''},
                  'pool': 'general',
                  'jobtypes': ['mochitest', 'mochitest-chrome', 'browser-chrome', 'reftest', 'crashtest', 'js-reftest', 'xpcshell']
                 }
        # Check to see if this rule exists, create if not
        result = self.db.views.jobmap.byBuild(key=jobmap['build'])
        if (len(result) is 0):
            self.db.create(jobmap)
            
        # And now one for default winmo fennec
        jobmap['build'] = '.*fennec.*wince-arm.zip'
        jobmap['testpackage'] = 'xulrunner.*wince-arm\.tests\.tar\.bz2'
        jobmap['platform']['os.sysname'] = 'winmo'
        result = self.db.views.jobmap.byBuild(key=jobmap['build'])
        if (len(result) is 0):
            self.db.create(jobmap)
        
        # And one for firefoxCE
        jobmap['build'] = '.*firefox.*wince-arm\.zip'
        jobmap['product'] = 'firefoxce'
        jobmap['testpackage'] = 'firefox.*wince-arm\.tests\.tar\.bz2'
        jobmap['platform']['os.sysname'] = 'wince'
        jobmap['platform']['hardware'] = 'mobinova' # we want to ensure this is mobinova tests
        result = self.db.views.jobmap.byBuild(key=jobmap['build'])
        if (len(result) is 0):
            self.db.create(jobmap)

    def POST(self, request, collection, resource=None):
        print "testBotAPI::Post request = " + str(request)
        if collection == 'getJob':
            print "getJobSERVER request.body = " + str(request.body)
            client_dict = json.loads(str(request.body))
            print "getJobSERVER client_dict = " + str(client_dict)

            client = self.db.get(client_dict['_id'])
            if dict(client) != client_dict:
                client.update(client_dict)
            
            job = self.manager.get_job(client)
            print "manager gave us this job: " + str(job)
            if job is not None:
                job.status = 'locked'
                self.db.save(job)
                return JSONResponse(job)
            return Response204()
            
        if collection == 'newBuild':
            build = json.loads(str(request.body))
            build['type'] = 'build'
            if 'timestamp' not in build:
                build['timestamp'] = datetime.now().isoformat()
            build_info = self.db.create(build)
            build['_id'] = build_info['id']
            build['_rev'] = build_info['rev']
            jobs = self.manager.new_build(build)
            if jobs is None:
                jobs = []
            for job in jobs:
                job['type'] = 'job'
                job['status'] = 'pending'
                if 'creationdt' not in job:
                    job['creationdt'] = datetime.now().isoformat()
            jobs_info = self.db.create(jobs)
            for i in range(len(jobs_info)):
                jobs[i]['_id'] = jobs_info[i]['id']
                jobs[i]['_rev'] = jobs_info[i]['rev']
            # We re-get the build document because the manager.new_build call may have modified it
            return JSONResponse({'build':self.db.get(build_info['id']),'jobs':jobs})
        
        if collection == 'heartbeat':
            client = self.db.get(resource)
            status = json.loads(str(request.body))
            if client.get('status', None) != status:
                client.status = status
                info = self.db.save(client)
            return JSONResponse(info)
        
        if collection == 'report':
            job = self.db.get(resource)
            try:
                report = json.loads(str(request.body))
            except:
                print "Server report function threw a error with: " + str(request.body)
            # Add in support for report handlers
            return JSONResponse(report) # Debug response

    def GET(self, request, collection):
        if collection == 'whoami':
            name = request.query['name']
            assert name
            result = self.db.views.clients.byName(key=name)
#          print "REGISTER whoami" + str(result)
            if len(result) is 0:
                info = self.db.create({"type":"client", "name":name})
 #               print "registering with " + str(info)
                return JSONResponse(self.db.get(info['id']))
            else:
#                 pass
#                print "register returns with : " + str(result[0])
               return JSONResponse(result[0])

        # Registering a device must be as simple as possible, just read key
        # value pairs from command line, generate a document from that        
        if collection == 'registerdevice':
            print "request.query = " + str(request.query)
            assert request.query['NAME']
                        
            # Find the device in the database
            result = self.db.views.devices.byName(key=request.query['NAME'])
            if len(result) is 0:
                # create record for device
                devicerecord = self.db.create({"type":"device",
                                               "name":request.query["NAME"],
                                               "ip":request.query["IPADDR"],
                                               "cmdport":request.query["CMDPORT"],
                                               "dataport":request.query["DATAPORT"],
                                               "os":request.query["OS"],
                                               "osversion":request.query["OSVERSION"],
                                               "screenw":request.query["SCRNWIDTH"],
                                               "screenh":request.query["SCRNHEIGHT"],
                                               "bpp":request.query["BPP"],
                                               "memory":request.query["MEMORY"],
                                               "hardware": request.query["HARDWARE"],
                                               "pool":request.query["POOL"],
                                               "product":request.query["PRODUCT"],
                                               "status":"free"}) 
                return JSONResponse(self.db.get(devicerecord['id']))
            else:
                # Ensure data in database is correct, we'll just update,
                # there can only be one device per device name in the db
                assert (len(result) is 1)
                rec = result[0]
                rec["name"] = request.query["NAME"]
                rec["ip"] = request.query["IPADDR"]
                rec["cmdport"] = request.query["CMDPORT"]
                rec["dataport"] = request.query["DATAPORT"]
                rec["os"] = request.query["OS"]
                rec["osversion"] =request.query["OSVERSION"]
                rec["screenw"] = request.query["SCRNWIDTH"]
                rec["screenh"] = request.query["SCRNHEIGHT"]
                rec["bpp"] = request.query["BPP"]
                rec["memory"] = request.query["MEMORY"]
                rec["hardware"] = request.query["HARDWARE"]
                rec["product"] = request.query["PRODUCT"]
                rec["pool"] = request.query["POOL"]
                # The device agent only registers once, so if we already know
                # about this device, chances are it was rebooted, so mark it
                # as free
                rec["status"] = "free"
                info = self.db.update(rec)
                return JSONResponse(info)



