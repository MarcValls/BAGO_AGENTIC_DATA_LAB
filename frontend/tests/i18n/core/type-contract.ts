import {t,localMessage} from '../../../src/i18n'
// Compile-only examples: this module is never imported by the application.
t('common.close')
t('core.App.p0_view_b10ac6',{p0:'fixture'})
localMessage('core.App.p0_view_b10ac6',{p0:'fixture'})
// @ts-expect-error Unknown catalog keys must fail.
t('missing.translation.key')
// @ts-expect-error A parameterized literal key requires its placeholders.
t('core.App.p0_view_b10ac6')
// @ts-expect-error Incorrect placeholder names must fail.
t('core.App.p0_view_b10ac6',{wrong:'fixture'})
// @ts-expect-error Local descriptors use the same parameter contract.
localMessage('core.App.p0_view_b10ac6')
