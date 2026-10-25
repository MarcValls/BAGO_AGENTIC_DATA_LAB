/** Synthetic metadata only: no providers, credentials, requests or workspace binding. */
export const runtimeStatusFixture = () => ({
 schema:'runtime-status.v1',checked_at:'2026-10-25T12:00:00Z',backend:{responding:true},
 activity:{state:'idle',active_requests:0,scope:'current_process_http_api_requests',background_activity:'not_observed'},
 memory:{state:'available',history:{kind:'conversation_history',state:'absent',proof:'metadata_presence_only'},general:{state:'disconnected'},checked_at:'2026-10-25T12:00:00Z',error_code:null},
 provider:{state:'not_configured',label:null,model:null,observation:'registration_metadata',response_verified:false,checked_at:'2026-10-25T12:00:00Z',error_code:null},
 git:{state:'not_repository',repo_detected:false,branch:null,detached:false,remote_configured:false,remote_verification:'not_checked',checked_at:'2026-10-25T12:00:00Z',cached:false,cache_ttl_seconds:5,error_code:null},
})
