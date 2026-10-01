import ast, asyncio, importlib, pathlib, sys, types, unittest, json
from unittest.mock import AsyncMock
root=pathlib.Path(__file__).resolve().parents[2] / 'custom_components/emaktab'
pkg=types.ModuleType('emaktab_test'); pkg.__path__=[str(root)]; sys.modules[pkg.__name__]=pkg
am=importlib.import_module('emaktab_test.auth'); api=importlib.import_module('emaktab_test.api')
class Response:
 def __init__(self,status,data=None): self.status=status; self.data=data
 async def __aenter__(self): return self
 async def __aexit__(self,*args): pass
 async def json(self,**kwargs): return self.data
class Session:
 def __init__(self,responses): self.responses=iter(responses)
 def get(self,*args,**kwargs):
  assert kwargs['allow_redirects'] is False
  return next(self.responses)
class Tests(unittest.IsolatedAsyncioTestCase):
 def test_form_captcha_hidden_and_action(self):
  p=am._LoginFormParser('https://login.emaktab.uz/login')
  p.feed('<form action="/submit"><input name="token" type="hidden" value="abc"><input name="login" type="text"><input name="password" type="password"><input name="Captcha.Input"></form>')
  self.assertTrue(p.found); self.assertEqual(p.username_field,'login'); self.assertEqual(p.password_field,'password'); self.assertEqual(p.hidden,{'token':'abc'}); self.assertEqual(p.action,'https://login.emaktab.uz/submit')
 def test_multiple_forms(self):
  p=am._LoginFormParser(); p.feed('<form><input name="search"></form><form><input name="email" type="email"><input name="pass" type="password"></form><form><input name="search"></form>')
  self.assertEqual(p.username_field,'email'); self.assertEqual(p.password_field,'pass')
 def test_missing_form(self):
  p=am._LoginFormParser(); p.feed('<html>maintenance</html>'); self.assertFalse(p.found)
 async def test_expiry_renews_once(self):
  for status in (302,401,403):
   auth=am.EmaktabAuthManager('test','test'); auth._session=Session([Response(status),Response(200,{'days':[]})]); auth.async_login=AsyncMock()
   result=await api.EmaktabApiClient(auth)._async_request_diary('https://emaktab.uz/api',{})
   self.assertEqual(result,{'days':[]}); auth.async_login.assert_awaited_once()
 async def test_repeated_expiry_stops(self):
  auth=am.EmaktabAuthManager('test','test'); auth._session=Session([Response(302),Response(302)]); auth.async_login=AsyncMock()
  with self.assertRaisesRegex(RuntimeError,'after re-login'): await api.EmaktabApiClient(auth)._async_request_diary('https://emaktab.uz/api',{})
  auth.async_login.assert_awaited_once()
 def test_ten_point_marks(self):
  tree=ast.parse((root/'sensor.py').read_text()); fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_normalize_lessons')
  ns={'Any':object}; exec(compile(ast.Module(body=[fn],type_ignores=[]),'sensor.py','exec'),ns)
  for value in (5,6,9,10,'10'):
   result=ns['_normalize_lessons']({'lessons':[{'workMarks':[{'marks':[{'value':value}]}]}]})
   self.assertEqual(int(result[0]['mark']['value']),int(value))
 def test_school_transfer(self):
  resolve=api.EmaktabApiClient._current_school_from_page
  def page(items): return 'var data = '+json.dumps({'schoolMemberships':items})
  primary={'personId':'child','schoolId':'new','isOo':True,'isOdo':False}
  club={'personId':'child','schoolId':'club','isOo':False,'isOdo':True}
  self.assertEqual(resolve(page([primary,club]),'child','old'),'new')
  self.assertIsNone(resolve(page([primary,club]),'child','new'))
  self.assertIsNone(resolve(page([primary]),'another-child','old'))
  self.assertIsNone(resolve(page([primary,dict(primary,schoolId='second')]),'child','old'))
  self.assertIsNone(resolve('broken page','child','old'))
  self.assertIsNone(resolve('"schoolMemberships":invalid','child','old'))
 async def test_school_transfer_retry_and_cache(self):
  client=api.EmaktabApiClient(types.SimpleNamespace(ensure_logged_in=AsyncMock()))
  client._async_find_current_school=AsyncMock(return_value='new')
  calls=[]
  async def request(url,params):
   calls.append(dict(params)); return {'days':[]} if params['schoolId']=='old' else {'days':[{'date':'1'}]}
  client._async_request_diary=request
  for _ in range(2):
   result=await client.async_get_diary('child','old'); self.assertEqual(len(result['days']),1)
  self.assertEqual([c['schoolId'] for c in calls],['old','new','new'])
  client._async_find_current_school.assert_awaited_once()
if __name__ == '__main__':
 unittest.main()
