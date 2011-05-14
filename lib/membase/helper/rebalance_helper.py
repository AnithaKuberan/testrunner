import time
import logger
from membase.api.rest_client import RestConnection, RestHelper
from membase.helper.bucket_helper import BucketOperationHelper
from memcached.helper.data_helper import MemcachedClientHelper

log = logger.Logger.get_logger()

class RebalanceHelper():

    @staticmethod
    def wait_till_total_numbers_match(master,
                                      servers,
                                      bucket,
                                      port,
                                      replica_factor,
                                      timeout_in_seconds=120):
        log.info('waiting for sum_of_curr_items == total_items....')
        start = time.time()
        verified = False
        while (time.time() - start) <= timeout_in_seconds:
            if RebalanceHelper.verify_items_count(master, servers, bucket, replica_factor):
                verified = True
                break
            else:
                time.sleep(2)
        rest = RestConnection(master)
        nodes_for_stats = rest.node_statuses()
        for node in nodes_for_stats:
            client = MemcachedClientHelper.create_memcached_client(node.ip, bucket, port)
            log.info("getting tap stats.. for {0}".format(node.ip))
            tap_stats = client.stats('all')
            interesting_stats = ['ack_log_size', 'ack_seqno', 'ack_window_full', 'has_item', 'has_queued_item',
                                 'idle', 'paused', 'pending_backfill', 'pending_disk_backfill', 'recv_ack_seqno',
                                 'ep_num_new_']
            for name in tap_stats:
                if name in interesting_stats:
                    log.info("TAP {0} :{1}   {2}".format(node.id, name, tap_stats[name]))
            client.close()
        return verified


    @staticmethod
    def verify_items_count(master,servers,bucket,replica_factor):
        rest = RestConnection(master)
        master_stats = rest.get_bucket_stats(bucket)
        all_server_stats = []
        for server in servers:
            #get the stats
            server_stats = rest.get_bucket_stats_for_node(bucket, server.ip)
            all_server_stats.append(server_stats)
        sum = 0
        for single_stats in all_server_stats:
            sum += single_stats["curr_items"]
        log.info('sum : {0}'.format(sum))
        log.info('master_stats : {0}'.format(master_stats["curr_items_tot"]))
        return (sum * (replica_factor + 1)) == master_stats["curr_items_tot"]


    @staticmethod
    def verify_maps(vbucket_map_before,vbucket_map_after):
        #for each bucket check the replicas
        for i in range(0,len(vbucket_map_before)):
            if not vbucket_map_before[i].master == vbucket_map_after[i].master:
                log.error(
                    'vbucket[{0}].master mismatch {1} vs {2}'.format(i,vbucket_map_before[i].master,vbucket_map_after[i].master))
                return False
            for j in range(0,len(vbucket_map_before[i].replica)):
                if not (vbucket_map_before[i].replica[j]) == (vbucket_map_after[i].replica[j]):
                    log.error('vbucket[{0}].replica[{1} mismatch {2} vs {3}'.format(i,j,
                        vbucket_map_before[i].replica[j],vbucket_map_after[i].replica[j] ))
                    return False
        return True

    @staticmethod
    def delete_all_buckets_or_assert(ips,test_case):
        log.info('deleting existing buckets on {0}'.format(ips))
        for ip in ips:
            rest = RestConnection(ip=ip,
                                  username='Administrator',
                                  password='password')
            buckets = rest.get_buckets()
            for bucket in buckets:
                print bucket.name
                rest.delete_bucket(bucket.name)
                log.info('deleted bucket : {0}'.format(bucket.name))
                msg = 'bucket "{0}" was not deleted even after waiting for two minutes'.format(bucket.name)
                test_case.assertTrue(BucketOperationHelper.wait_for_bucket_deletion(bucket.name, rest, 200)
                                , msg=msg)

    @staticmethod
    def wait_for_bucket_deletion(bucket,
                                 rest,
                                 timeout_in_seconds=120):
        log.info('waiting for bucket deletion to complete....')
        start = time.time()
        helper = RestHelper(rest)
        while (time.time() - start) <= timeout_in_seconds:
            if not helper.bucket_exists(bucket):
                return True
            else:
                time.sleep(2)
        return False

    @staticmethod
    def wait_for_bucket_creation(bucket,
                                 rest,
                                 timeout_in_seconds=120):
        log.info('waiting for bucket creation to complete....')
        start = time.time()
        helper = RestHelper(rest)
        while (time.time() - start) <= timeout_in_seconds:
            if helper.bucket_exists(bucket):
                return True
            else:
                time.sleep(2)
        return False

    # in this method
#    @staticmethod
#    def add_node_and_rebalance(rest,node_ip):
#        pass
        #read the current nodes
        # if the node_ip already added then just
        #silently return
        #if its not added then let try to add this and then rebalance
        #we should alo try to get the bucket information from
        #rest api instead of passing it to the fucntions
        
        
        