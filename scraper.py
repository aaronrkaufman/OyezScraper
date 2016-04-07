import codecs
import unicodecsv as csv
import datetime
import json
import os
import time
import requests

class OyezScraper:
    def __init__(self, year_start, year_end):
        self.show_debug = True
        self.saved_data = {'all_cases': {},
                           'case_details':{},
                           'transcripts':{},
                           'transcript':{},
                           'script_text':{},
                           'read_scripts':{}}

        self.base_dir = self.mk_base_dir('./{}'.format(str(year_start)))
        self.load_data()
        self.year_start = year_start
        self.year_end = year_end

        self.limit_rate = 0

    def mk_base_dir(self, path):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            os.makedirs(path)
            os.makedirs(os.path.join(path, 'transcripts'))
            os.makedirs(os.path.join(path, 'transcripts_cleaned'))
            os.makedirs(os.path.join(path, 'output'))
        return path
            
    def mypath(self, path):
        this_path =  os.path.join(self.base_dir, path)
        # self.debug("path_name: {}".format(this_path))
        return this_path
        
    def load_data(self):
        for name, default in self.saved_data.items():
            try:
                fn = self.mypath("{}.json".format(name))
                with open(fn, 'r') as fh:
                    setattr(self, name, (json.loads(fh.read())))
            except:
                setattr(self, name, default)

    def save_data(self, data, filename):
        filename = self.mypath(filename)
        with open(filename, 'w') as fh:
            fh.write(json.dumps(data))

    def log(self, msg):
        print(msg)

    def debug(self, msg):
        if self.show_debug == True:
            print(msg)
        
    def fetch(self, url, saved_data, filename):
        if not url in saved_data.keys():
            self.log("Fetching: {}".format(url))
            doc = requests.get(url)
            saved_data[url] = doc.json()
            self.save_data(saved_data, filename)
            time.sleep(self.limit_rate)
        else:
            self.debug("Not fetching: {}".format(url))
            
    def get_all_cases(self):
        base_url = 'https://api.oyez.org/cases?filter=term:{}&labels=true&page=0&per_page=0'
        # for i in range(self.year_start, self.year_end):
        url = base_url.format(self.year_start)
        self.fetch(url, self.all_cases, 'all_cases.json')

    def get_case_details(self):
        for url, cases in self.all_cases.items():
            for case in cases:
                url = case['href']
                self.fetch(url, self.case_details, 'case_details.json')

    def get_scripts(self):
        for url, case in self.case_details.items():
            self.transcript = {}
            if case['oral_argument_audio']: # Some cases do not have audio available
                for item in case['oral_argument_audio']:
                    url = item['href']
                    filename = self.mypath('transcripts/{}.json'.format(url.split('oral_argument_audio/')[1]))
                    if not os.path.isfile(filename):
                        self.fetch(url, self.transcript, filename)
                        self.transcripts[url] = filename
                        self.save_data(self.transcripts, 'transcripts.json')
                    else:
                        self.debug("Not fetching: {}".format(url))

    def load_transcript(self, key):
        filename = self.mypath(self.transcripts[key])
        with open(filename, 'r') as fh:
            self.transcript = json.loads(fh.read())
                        
    def case_attrs(self):
        for url, case in self.case_details.items():
            if case['oral_argument_audio']: # Some cases do not have audio available
                for item in case['oral_argument_audio']:
                    url = item['href']
                    if url in self.transcripts.keys():
                        self.load_transcript(url)
                        self.transcript[url]['docket_number'] = case['docket_number']
                        self.save_data(self.transcript, self.transcripts[url])
                    
    def get_script_text(self):
        for url, filename in self.transcripts.items():
            filename = self.mypath('transcripts_cleaned/{}.json'.format(url.split('oral_argument_audio/')[1]))
            if not os.path.isfile(filename):
                self.load_transcript(url)
                this_transcript = self.transcript[url]
                self.log("Processing: {}".format(url))
                self.read_script(filename)
            else:
                self.log("Already read: {}".format(url))

    def get_transcript_name(self, transcript):
        name = transcript['title'].replace(' ', '_') + '-' + str(transcript['id'])
        name = name.replace('Oral_Argument_-_', '')
        return name

    def read_script(self, filename):
        filename = self.mypath(filename)
        for url, transcript in self.transcript.items():
            # if not 'docket_number' in transcript.keys():
            docket = self.get_transcript_name(transcript)
            # else:
            #     docket = transcript['docket_number']
            self.script_text[docket] = []
            if not transcript['transcript']:
                self.debug('No transcript: {}'.format(url))
                continue

            for section in transcript['transcript']['sections']:
                for turn in section['turns']:
                    if not turn['speaker']:
                        turn['speaker'] = {'name':'---'}

                    speaker = turn['speaker']['name']
                    for text_block in turn['text_blocks']:
                        start = float(text_block['start'])
                        start = str(datetime.timedelta(seconds=start))
                        stop = float(text_block['stop'])
                        stop = str(datetime.timedelta(seconds=stop))
                        self.script_text[docket].append([speaker, start, stop, text_block['text']])
            self.read_scripts[docket] = filename
            self.save_data(self.read_scripts, 'read_scripts.json')
            self.save_data(self.script_text, filename)

    def load_processed_script(self, filename):
        filename = self.mypath(filename)
        with open(filename, 'r') as fh:
            script = json.loads(fh.read())
            return script[script.keys()[0]]
            
    def output_csv_json(self):
        for docket, path in self.read_scripts.items():
            filename = self.mypath('output/{}.csv'.format(docket))
            if not os.path.isfile(filename):
                self.log("Writing output: {}".format(filename))
                script = self.load_processed_script(path)
                with open(filename, 'wb') as fh:
                    writer = csv.writer(fh)
                    writer.writerows(script)
            else:
                self.debug("File already exists: {}".format(filename))
                    
            filename = self.mypath('output/{}.json'.format(docket))
            if not os.path.isfile(filename):
                self.log("Writing output: {}".format(filename))
                script = self.load_processed_script(path)
                with open(filename, 'w') as fh:
                    fh.write(json.dumps(script))
            else:
                self.debug("File already exists: {}".format(filename))
                        
    def run(self):
        self.get_all_cases()
        self.get_case_details()
        self.get_scripts()
        self.case_attrs()
        self.get_script_text()
        self.output_csv_json()

# if __name__ == '__main__':
#     scraper = OyezScraper(1960, 2016)
#     scraper.run()
