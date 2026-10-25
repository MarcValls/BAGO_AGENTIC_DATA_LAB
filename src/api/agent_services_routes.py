"""Host review endpoints. No mutation function is advertised to the model."""
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field

from src.agent_tools.agent_services import review_filesystem,execute_filesystem,DELIVERY_TOOL_IDS
from src.services.agent_producers import ProducerStore


REVIEW_TEMPLATE=json.loads((Path(__file__).resolve().parents[1]/'agent_tools/profiles/delivery-reviewer.json').read_text(encoding='utf8'))


class FilesystemReviewRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    owner_id:str=Field(min_length=1,max_length=128)
    conversation_id:str=Field(min_length=1,max_length=128)
    revision:int=Field(ge=0)


class FilesystemExecuteRequest(FilesystemReviewRequest):
    review_token:str=Field(min_length=1,max_length=128)
    plan_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    confirmed:bool=Field(strict=True)


def create_agent_services_router(*,workspace_root,load_agent,owned_conversation,communications):
    router=APIRouter()
    def origin(request):
        value=request.headers.get('origin')
        if value and (urlsplit(value).scheme,urlsplit(value).netloc)!=(urlsplit(str(request.base_url)).scheme,urlsplit(str(request.base_url)).netloc):raise HTTPException(403,detail={'code':'origin_rejected'})
    def bound(body):
        agent=load_agent(body.owner_id)
        if 'filesystem_plan' not in getattr(agent.config,'tools',[]):raise HTTPException(403,detail={'code':'filesystem_tool_not_assigned'})
        conversation=owned_conversation(body.conversation_id,'agent',body.owner_id)
        if conversation['revision']!=body.revision or conversation['status']!='active':raise HTTPException(409,detail={'code':'filesystem_conversation_changed','message':'La conversación cambió. Revisa de nuevo el plan.'})
        return agent

    @router.get('/api/agent-tools/templates')
    async def templates():
        return {'templates':[{'id':'delivery-reviewer','label':'Revisor de entregas','config':REVIEW_TEMPLATE}]}

    @router.get('/api/agent-tools/context')
    async def context(owner_id:str,request:Request):
        origin(request)
        agent=load_agent(owner_id);tools=set(getattr(agent.config,'tools',[]))
        if not tools&DELIVERY_TOOL_IDS:return {'runs':[],'contacts':[]}
        try:
            runs=ProducerStore(workspace_root()).list()
            for run in runs:
                try:run['producer_name']=load_agent(run['owner_id']).config.name
                except (HTTPException,AttributeError):run['producer_name']=run['owner_id']
            return {'runs':runs,'contacts':communications().contacts()}
        except (ValueError,OSError,KeyError) as error:raise HTTPException(422,detail={'code':'review_context_unavailable','message':str(error)}) from None

    @router.post('/api/agent-tools/filesystem/{proposal_id}/review')
    async def review(proposal_id:str,body:FilesystemReviewRequest,request:Request):
        origin(request);bound(body)
        try:return await asyncio.to_thread(review_filesystem,workspace=workspace_root(),proposal_id=proposal_id,
            owner_id=body.owner_id,conversation_id=body.conversation_id,revision=body.revision)
        except (ValueError,OSError,KeyError) as error:raise HTTPException(422,detail={'code':'filesystem_review_rejected','message':str(error)}) from None

    @router.post('/api/agent-tools/filesystem/{proposal_id}/execute')
    async def execute(proposal_id:str,body:FilesystemExecuteRequest,request:Request):
        origin(request);bound(body)
        try:return await asyncio.to_thread(execute_filesystem,workspace=workspace_root(),proposal_id=proposal_id,
            owner_id=body.owner_id,conversation_id=body.conversation_id,revision=body.revision,
            review_token=body.review_token,plan_sha256=body.plan_sha256,confirmed=body.confirmed)
        except (ValueError,OSError,KeyError) as error:raise HTTPException(422,detail={'code':'filesystem_execute_rejected','message':str(error)}) from None
    return router
