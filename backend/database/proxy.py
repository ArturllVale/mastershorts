from .operations import (
    get_job, create_or_update_job, update_job_status, append_job_log,
    update_job_field, update_job_dict_field, delete_job, get_all_jobs, job_exists
)

class DBJobsProxy:
    def __contains__(self, key):
        return job_exists(key)
        
    def __getitem__(self, key):
        if not job_exists(key):
            raise KeyError(key)
        # return a proxy dictionary that captures modifications
        return JobDictProxy(key, get_job(key))
        
    def __setitem__(self, key, value):
        create_or_update_job(key, value)
        
    def __delitem__(self, key):
        delete_job(key)
        
    def get(self, key, default=None):
        if job_exists(key):
            return self[key]
        return default
        
    def pop(self, key, default=None):
        if job_exists(key):
            val = get_job(key)
            delete_job(key)
            return val
        return default

    def values(self):
        return get_all_jobs()
        
    def keys(self):
        return [j['id'] for j in get_all_jobs()]
        
    def items(self):
        return [(j['id'], j) for j in get_all_jobs()]

class JobDictProxy(dict):
    def __init__(self, job_id, data):
        super().__init__(data)
        self.job_id = job_id
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        update_job_field(self.job_id, key, value)
        
    def __getitem__(self, key):
        val = super().__getitem__(key)
        if isinstance(val, list):
            if key == 'logs':
                return LogListProxy(self.job_id, val)
        if isinstance(val, dict):
            return SubDictProxy(self.job_id, key, val)
        return val

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

class LogListProxy(list):
    def __init__(self, job_id, data):
        super().__init__(data)
        self.job_id = job_id
        
    def append(self, val):
        super().append(val)
        append_job_log(self.job_id, val)

class SubDictProxy(dict):
    def __init__(self, job_id, field, data):
        super().__init__(data)
        self.job_id = job_id
        self.field = field
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        update_job_dict_field(self.job_id, self.field, key, value)
        
    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]
