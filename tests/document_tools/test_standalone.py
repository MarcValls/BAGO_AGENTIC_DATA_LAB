"""Finite acceptance over generated synthetic input, never the user corpus."""
from pathlib import Path
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/document-toolkit"))
from document_toolkit import Limits, capabilities, execute
from document_toolkit.core import canonical, digest


def zip_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        for name, payload in entries.items():
            z.writestr(name, payload)
    return stream.getvalue()


def fixtures(root):
    (root / "invoice.txt").write_text("FAC-2025001 EUR 120.00\n=SUM(A1:A2)\n", encoding="utf8")
    (root / "transfer.csv").write_text('ref;currency;amount\nFAC-2025001;EUR;120.00\n', encoding="utf8")
    (root / "payment.txt").write_text("FAC-2025001 EUR 120.00\n", encoding="utf8")
    (root / "message.eml").write_bytes(b'From: test@example.invalid\r\nTo: customer@example.invalid\r\nSubject: FAC-2025001\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nReference FAC-2025001 EUR 120.00\r\n')
    (root / "letter.docx").write_bytes(zip_bytes({"word/document.xml": '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>FAC-2025001</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>EUR 120.00</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'''}))
    (root / "ledger.xlsx").write_bytes(zip_bytes({
        "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sales" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>FAC-2025001</t></is></c><c r="B1"><f>60+60</f><v>120</v></c></row></sheetData></worksheet>'}))
    try:
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        writer = PdfWriter(); page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 30 700 Td (FAC-2025001 EUR 120.00) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(stream)
        writer.write(str(root / "invoice.pdf"))
    except ImportError:
        pass
    try:
        from PIL import Image, ImageDraw
        image=Image.new('RGB',(800,120),'white'); ImageDraw.Draw(image).text((30,30),'FAC-2025001 EUR 120.00',fill='black',font_size=40)
        image.save(root/'scan.png')
    except ImportError:
        pass


class StandaloneAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='document-toolkit-synthetic-')
        self.root=Path(self.temp.name)/'source'; self.root.mkdir()
        fixtures(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def extract(self, paths=None, **args):
        return execute('extract',self.root,{'paths': paths or ['invoice.txt','payment.txt'],**args})

    def test_multiformat_exact_locations_and_unavailable_ocr(self):
        dependency = capabilities()['formats']['.pdf']['dependency']
        self.assertEqual(dependency, 'pypdf==6.21.4')
        self.assertIn(dependency, (REPO/'requirements-documents.txt').read_text().splitlines())
        metadata = tomllib.loads((REPO/'tools/document-toolkit/pyproject.toml').read_text())
        self.assertEqual(metadata['project']['optional-dependencies']['pdf'], [dependency])
        names=['invoice.txt','transfer.csv','message.eml','letter.docx','ledger.xlsx']
        if capabilities()['formats']['.pdf']['available']:names.append('invoice.pdf')
        result=self.extract(names)
        self.assertEqual(result['state'],'EXECUTED',result)
        byname={r['source']['path']:r for r in result['records']}
        self.assertEqual(byname['letter.docx']['segments'][1]['location'],{'table':1,'row':1,'column':1})
        formula=byname['ledger.xlsx']['segments'][1]
        self.assertEqual(formula['text'],'=60+60'); self.assertEqual(formula['cached_value'],'120');self.assertFalse(formula['recalculated'])
        self.assertEqual(formula['location'],{'sheet':'Sales','cell':'B1'})
        self.assertEqual(byname['transfer.csv']['segments'][3]['location'],{'row':2,'column':1})
        self.assertEqual(byname['message.eml']['segments'][0]['location'],{'header':'From'})
        for record in result['records']:
            self.assertEqual(record['source']['sha256'],hashlib.sha256((self.root/record['source']['path']).read_bytes()).hexdigest())
        if (self.root/'scan.png').exists():
            scan=self.extract(['scan.png'])
            if capabilities()['formats']['.png']['available']:
                self.assertEqual(scan['state'],'EXECUTED',scan)
                self.assertTrue(all('bbox' in s['location'] for s in scan['records'][0]['segments']))
            else:
                self.assertEqual(scan['errors'][0]['code'],'OCR_ENGINE_UNAVAILABLE')

    def test_inventory_partial_recovery_and_stale_rejection(self):
        selected=['invoice.txt','broken.pdf','payment.txt']
        (self.root/'broken.pdf').write_bytes(b'not pdf')
        first=self.extract(selected)
        self.assertEqual(first['state'],'PARTIAL');self.assertEqual(len(first['records']),2)
        resumed=self.extract(['invoice.txt','payment.txt'],resume=first)
        self.assertEqual(resumed['records'],first['records'])
        (self.root/'invoice.txt').write_text('changed',encoding='utf8')
        stale=self.extract(['invoice.txt'],resume=first)
        self.assertEqual(stale['state'],'FAILED');self.assertEqual(stale['errors'][0]['code'],'STALE_SOURCE')
        inventory=execute('inventory',self.root,{'paths':['payment.txt']})
        self.assertEqual(inventory['state'],'EXECUTED')

    def test_boundaries_and_limits(self):
        for path in ['../outside.txt','C:/private.txt','invoice.txt:secret']:
            self.assertEqual(self.extract([path])['state'],'FAILED')
        limit=execute('extract',self.root,{'paths':['invoice.txt']},limits=Limits(max_file_bytes=4))
        self.assertEqual(limit['errors'][0]['code'],'FILE_BYTE_LIMIT')
        clipped=execute('extract',self.root,{'paths':['invoice.txt']},limits=Limits(max_chars=3))
        self.assertEqual(clipped['state'],'PARTIAL'); self.assertTrue(clipped['truncated'])
        with self.assertRaises(ValueError):Limits(max_files=0)
        try:
            (self.root/'linked.txt').symlink_to(self.root/'invoice.txt')
        except OSError:
            pass
        else:
            self.assertEqual(self.extract(['linked.txt'])['errors'][0]['code'],'LINK_REJECTED')

    def test_relation_candidates_never_confirm_payment(self):
        result=execute('relate',self.root,{'bundle':self.extract()})
        self.assertEqual(result['state'],'EXECUTED')
        self.assertTrue(result['relations']);self.assertFalse(result['conclusions_confirmed'])
        self.assertTrue(all(not r['payment_confirmed'] and len(r['evidence'])==2 for r in result['relations']))
        (self.root/'payment.txt').write_text('FAC-2025001 USD 999.00',encoding='utf8')
        contradictory=execute('relate',self.root,{'bundle':self.extract()})
        self.assertFalse(contradictory['relations'][0]['matching_amounts'])
        self.assertEqual(contradictory['relations'][0]['state'],'CANDIDATE')

    def test_missing_provenance_and_tampering_rejected(self):
        bad=self.extract();bad['records'][0]['segments'][0].pop('location')
        bad['bundle_sha256']=digest(canonical(bad['records']))
        result=execute('relate',self.root,{'bundle':bad})
        self.assertEqual(result['errors'][0]['code'],'MISSING_PROVENANCE')
        bad=self.extract();bad['records'][0]['segments'][0]['text']='invented'
        self.assertEqual(execute('relate',self.root,{'bundle':bad})['errors'][0]['code'],'BUNDLE_INTEGRITY')

    def test_export_no_overwrite_source_writes_and_csv_escaping(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        destination=Path(self.temp.name)/'export.csv'
        args={'bundle':self.extract(),'destination':str(destination),'format':'csv'}
        result=execute('export',self.root,args)
        self.assertEqual(result['state'],'EXECUTED',result)
        self.assertIn("'=SUM",destination.read_text(encoding='utf-8-sig'))
        self.assertEqual(result['output']['sha256'],hashlib.sha256(destination.read_bytes()).hexdigest())
        self.assertEqual(execute('export',self.root,args)['errors'][0]['code'],'OUTPUT_EXISTS_OR_MISSING')
        args['destination']=str(self.root/'new.json')
        self.assertEqual(execute('export',self.root,args)['errors'][0]['code'],'OUTPUT_MUST_BE_OUTSIDE_SOURCE_ROOT')
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()})

    def test_rename_plan_preconditions_names_and_collisions(self):
        entry={'path':'invoice.txt','destination':'2025_invoice.txt','expected_sha256':hashlib.sha256((self.root/'invoice.txt').read_bytes()).hexdigest()}
        good=execute('plan-rename',self.root,{'entries':[entry]})
        self.assertEqual(good['state'],'EXECUTED');self.assertFalse((self.root/'2025_invoice.txt').exists())
        for target in ['CON.txt','bad?.txt','payment.txt','invoice.txt','../escape.txt']:
            bad=execute('plan-rename',self.root,{'entries':[{**entry,'destination':target}]})
            self.assertEqual(bad['state'],'FAILED',target)

    def test_standard_cli_outside_repository_matches_api(self):
        env=dict(os.environ,PYTHONPATH=str(REPO/'tools/document-toolkit'))
        proc=subprocess.run([sys.executable,'-m','document_toolkit','inventory','--root',str(self.root),'--arguments','{"paths":["invoice.txt"]}'],cwd=self.temp.name,env=env,capture_output=True,text=True,encoding='utf8',timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['records'],execute('inventory',self.root,{'paths':['invoice.txt']})['records'])

    def test_xml_entities_and_archive_expansion_rejected(self):
        (self.root/'entity.docx').write_bytes(zip_bytes({'word/document.xml':'<!DOCTYPE x [<!ENTITY y "EXPANDED">]><x>&y;</x>'}))
        bad=self.extract(['entity.docx'])
        self.assertEqual(bad['errors'][0]['code'],'XML_ENTITY_REJECTED')
        (self.root/'large.docx').write_bytes(zip_bytes({'word/document.xml':'X'*2000}))
        expanded=execute('extract',self.root,{'paths':['large.docx']},limits=Limits(max_bytes=2100))
        self.assertEqual(expanded['state'],'FAILED')

    def test_fresh_rewrites_are_readable_with_windows_stat_fstat(self):
        from document_toolkit.core import stable_read
        for index in range(20):
            payload=('rewrite-'+str(index)).encode('utf8')
            (self.root/'rewrite.txt').write_bytes(payload)
            self.assertEqual(stable_read(self.root.resolve(),'rewrite.txt',1024),payload)


if __name__=='__main__': unittest.main()
