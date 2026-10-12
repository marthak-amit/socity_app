// Gujarati — scaffold: translated for the core flows, everything else falls back to English.
const gu = {
  common: {
    cancel: 'રદ કરો', save: 'સાચવો', done: 'થઈ ગયું', next: 'આગળ', back: 'પાછળ', retry: 'ફરી પ્રયાસ કરો', loading: 'લોડ થઈ રહ્યું છે…',
    error: 'કંઈક ખોટું થયું', offline: 'ઇન્ટરનેટ નથી. કૃપા કરીને તપાસીને ફરી પ્રયાસ કરો.', confirm: 'પુષ્ટિ કરો', delete: 'કાઢી નાખો',
    remove: 'દૂર કરો', edit: 'ફેરફાર કરો', search: 'શોધો', share: 'શેર કરો', copy: 'કૉપિ', copied: 'કૉપિ થયું', yes: 'હા', no: 'ના',
    free: 'મફત', approve: 'મંજૂર કરો', reject: 'નામંજૂર કરો', pending: 'બાકી', approved: 'મંજૂર', rejected: 'નામંજૂર',
    cancelled: 'રદ', continue: 'ચાલુ રાખો', today: 'આજે', create: 'બનાવો', add: 'ઉમેરો', close: 'બંધ કરો',
  },
  roles: { owner: 'માલિક', admin: 'એડમિન', volunteer: 'સ્વયંસેવક', member: 'સભ્ય' },
  tabs: { home: 'કાર્યક્રમો', passes: 'મારા પાસ', gallery: 'ગેલેરી', scan: 'સ્કેન', manage: 'મેનેજ' },
  auth: {
    welcome: 'તમારી સોસાયટીના કાર્યક્રમો અને પાસ', phoneLabel: 'મોબાઇલ નંબર', sendOtp: 'OTP મોકલો', invalidPhone: '10 અંકનો સાચો મોબાઇલ નંબર દાખલ કરો',
    otpTitle: 'તમારો નંબર ચકાસો', otpSent: 'અમે +91 {{phone}} પર 6 અંકનો કોડ મોકલ્યો છે', otpLabel: '6 અંકનો કોડ', verify: 'ચકાસો',
    resend: 'કોડ ફરી મોકલો', resendIn: '{{seconds}} સેકન્ડમાં ફરી મોકલો', invalidOtp: '6 અંકનો કોડ દાખલ કરો', yourName: 'અમે તમને શું કહીને બોલાવીએ?',
    namePlaceholder: 'પૂરું નામ',
  },
  onboarding: {
    title: 'સ્વાગત છે{{name}}!', subtitle: 'તમારી સોસાયટીમાં જોડાઓ અથવા નવી બનાવો.', join: 'સોસાયટીમાં જોડાઓ', joinSub: 'એડમિન પાસેથી મળેલો આમંત્રણ કોડ દાખલ કરો',
    create: 'સોસાયટી બનાવો', createSub: 'કાર્યક્રમો બનાવો અને પાસ વેચો', pendingTitle: 'મંજૂરીની રાહ', signOut: 'સાઇન આઉટ',
  },
  join: {
    title: 'સોસાયટીમાં જોડાઓ', codeLabel: 'આમંત્રણ કોડ', scanQr: 'આમંત્રણ QR સ્કેન કરો', find: 'સોસાયટી શોધો', wing: 'વિંગ / બ્લોક', flat: 'ફ્લેટ નંબર',
    request: 'જોડાવાની વિનંતી મોકલો', sent: 'વિનંતી મોકલાઈ! એડમિન જલ્દી જોશે.', invalidCode: 'આ કોડથી કોઈ સોસાયટી મળી નથી',
  },
  home: { upcoming: 'આગામી', past: 'ભૂતકાળ', emptyUpcoming: 'કોઈ આગામી કાર્યક્રમ નથી', soldOut: 'વેચાઈ ગયું', closed: 'બુકિંગ બંધ', createEvent: 'નવો કાર્યક્રમ' },
  event: { about: 'વિગત', venue: 'સ્થળ', when: 'ક્યારે', passes: 'પાસ', getPasses: 'પાસ મેળવો', bookingClosed: 'બુકિંગ બંધ છે', eventOver: 'કાર્યક્રમ પૂરો થયો' },
  buy: { title: 'પાસ પસંદ કરો', qty: 'સંખ્યા', holders: 'દરેક પાસ કોના માટે છે?', holderName: 'નામ', member: 'રહેવાસી', guest: 'મહેમાન', total: 'કુલ', continueToPay: 'ચુકવણી માટે આગળ વધો' },
  order: {
    awaitingPayment: 'ચુકવણીની રાહ', inReview: 'ચુકવણીની તપાસ ચાલુ છે', approvedTitle: 'ચુકવણી મંજૂર 🎉', payViaUpi: 'UPI એપથી ચુકવણી કરો',
    screenshot: 'ચુકવણીનો સ્ક્રીનશોટ', pickScreenshot: 'સ્ક્રીનશોટ પસંદ કરો', utr: 'UTR / સંદર્ભ નંબર', submitProof: 'મંજૂરી માટે મોકલો', viewPasses: 'મારા પાસ જુઓ',
  },
  passes: { title: 'મારા પાસ', empty: 'હજુ કોઈ પાસ નથી', offlineBanner: 'ઑફલાઇન — ફોનમાં સાચવેલા પાસ બતાવ્યા છે', showQr: 'ગેટ પર આ QR બતાવો', revoked: 'રદ' },
  gallery: { title: 'ગેલેરી', empty: 'હજુ કોઈ ફોટો નથી', upload: 'ફોટા અપલોડ કરો' },
  scan: { title: 'પાસ સ્કેન કરો', allowed: 'પ્રવેશની મંજૂરી', denied: 'પ્રવેશ ન આપો', scanned: 'સ્કેન', sold: 'વેચાયા', tapContinue: 'આગળ સ્કેન કરવા ટૅપ કરો' },
  manage: { title: 'મેનેજ', approvals: 'ચુકવણી મંજૂરી', events: 'કાર્યક્રમો', members: 'સભ્યો', reports: 'રિપોર્ટ', invite: 'રહેવાસીઓને આમંત્રણ', settings: 'સોસાયટી સેટિંગ' },
  settings: { title: 'સેટિંગ', language: 'ભાષા', signOut: 'સાઇન આઉટ', name: 'નામ' },
};
export default gu;
