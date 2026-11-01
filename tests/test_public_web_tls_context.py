"""TLS policy checks, no external network and no changes to OS trust/config."""
import ssl
import sys
from types import SimpleNamespace

import certifi
import pytest
from src.web_research import core


def clear_override(monkeypatch):
    monkeypatch.delenv('SSL_CERT_FILE',raising=False)
    monkeypatch.delenv('SSL_CERT_DIR',raising=False)


def test_existing_ca_bundle_adds_public_issuers_without_disabling_validation(monkeypatch):
    clear_override(monkeypatch)
    before=ssl.create_default_context().cert_store_stats()['x509_ca']
    context=core.verified_tls_context()
    assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname is True
    assert context.cert_store_stats()['x509_ca']>=before


@pytest.mark.parametrize('name',['SSL_CERT_FILE','SSL_CERT_DIR'])
@pytest.mark.parametrize('value',['explicit-operator-configuration',''])
def test_explicit_host_ca_configuration_is_preserved(monkeypatch,name,value):
    clear_override(monkeypatch)
    monkeypatch.setenv(name,value)
    expected=object()
    monkeypatch.setattr(core.ssl,'create_default_context',lambda:expected)
    monkeypatch.setattr(certifi,'where',lambda:pytest.fail('Do not override the operator trust source'))
    assert core.verified_tls_context() is expected


def test_standalone_sdk_without_optional_certifi_keeps_verified_default_context(monkeypatch):
    clear_override(monkeypatch)
    monkeypatch.setitem(sys.modules,'certifi',None)
    context=core.verified_tls_context()
    assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname is True


def test_invalid_installed_bundle_fails_instead_of_bypassing_tls(monkeypatch,tmp_path):
    clear_override(monkeypatch)
    path=tmp_path/'bad.pem';path.write_text('not a certificate',encoding='ascii')
    monkeypatch.setattr(certifi,'where',lambda:str(path))
    with pytest.raises(ssl.SSLError):core.verified_tls_context()


def test_untrusted_certificate_is_explicit_and_has_no_unverified_retry(monkeypatch):
    attempts=[];closed=[]
    sock=SimpleNamespace(settimeout=lambda value:None,close=lambda:closed.append(True))
    monkeypatch.setattr(core,'public_addresses',lambda *a,**k:['93.184.216.34','93.184.216.35'])
    monkeypatch.setattr(core.socket,'create_connection',lambda address,**k:attempts.append(address) or sock)
    def untrusted(*args,**kwargs):raise ssl.SSLCertVerificationError(1,'Synthetic untrusted certificate')
    monkeypatch.setattr(core,'verified_tls_context',lambda:SimpleNamespace(wrap_socket=untrusted))
    with pytest.raises(core.WebReadError) as error:core.https_get('https://example.com/',5)
    assert error.value.code=='TLS_VERIFICATION_FAILED'
    assert attempts==[('93.184.216.34',443)] and closed
