"""Host confirmation of one saved-agent task; never an advertised model execution tool."""
from urllib.parse import urlsplit
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from src.services.agent_delegation import DelegationError


class DelegationScope(BaseModel):
    model_config=ConfigDict(extra='forbid')
    allow_tools:bool=Field(default=False,strict=True)
    root:str|None=Field(default=None,max_length=1024)
    allow_export:bool=Field(default=False,strict=True)
    expected_output_directory:str|None=Field(default=None,max_length=1024)
    review_work_id:str|None=Field(default=None,max_length=128)
    review_candidate_id:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    review_scope_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    contact_id:str|None=Field(default=None,max_length=128)
    allow_draft:bool=Field(default=False,strict=True)


class DelegationExecuteRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    parent_conversation_id:str=Field(min_length=1,max_length=128)
    parent_revision:int=Field(ge=0)
    proposal_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    confirm:bool=Field(strict=True)
    scope:DelegationScope


def create_agent_delegation_router(*,service):
    router=APIRouter()
    def origin(request):
        value=request.headers.get('origin')
        if value and (urlsplit(value).scheme,urlsplit(value).netloc)!=(urlsplit(str(request.base_url)).scheme,urlsplit(str(request.base_url)).netloc):raise HTTPException(403,detail={'code':'origin_rejected'})

    @router.get('/api/agent-delegations/{proposal_id}')
    async def status(proposal_id:str,parent_conversation_id:str,request:Request):
        origin(request)
        try:
            instance=service();return {'agent_delegation':instance.public(instance.get(proposal_id,parent_conversation_id=parent_conversation_id))}
        except DelegationError as error:raise HTTPException(error.status,detail={'code':error.code}) from None

    @router.post('/api/agent-delegations/{proposal_id}/execute')
    async def execute(proposal_id:str,body:DelegationExecuteRequest,request:Request):
        origin(request)
        try:return await service().execute(proposal_id,**{**body.model_dump(),'scope':body.scope.model_dump()})
        except DelegationError as error:raise HTTPException(error.status,detail={'code':error.code}) from None
    return router
