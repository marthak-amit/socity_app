// Hindi — scaffold: translated for the core flows, everything else falls back to English.
const hi = {
  common: {
    cancel: 'रद्द करें', save: 'सहेजें', done: 'हो गया', next: 'आगे', back: 'पीछे', retry: 'फिर कोशिश करें', loading: 'लोड हो रहा है…',
    error: 'कुछ गड़बड़ हो गई', offline: 'इंटरनेट नहीं है। कृपया जाँचें और फिर कोशिश करें।', confirm: 'पुष्टि करें', delete: 'हटाएँ',
    remove: 'हटाएँ', edit: 'संपादित करें', search: 'खोजें', share: 'साझा करें', copy: 'कॉपी', copied: 'कॉपी हो गया', yes: 'हाँ', no: 'नहीं',
    free: 'निःशुल्क', approve: 'स्वीकृत करें', reject: 'अस्वीकार करें', pending: 'लंबित', approved: 'स्वीकृत', rejected: 'अस्वीकृत',
    cancelled: 'रद्द', continue: 'जारी रखें', today: 'आज', create: 'बनाएँ', add: 'जोड़ें', close: 'बंद करें',
  },
  roles: { owner: 'मालिक', admin: 'एडमिन', volunteer: 'स्वयंसेवक', member: 'सदस्य' },
  tabs: { home: 'कार्यक्रम', passes: 'मेरे पास', gallery: 'गैलरी', scan: 'स्कैन', manage: 'प्रबंधन' },
  auth: {
    welcome: 'आपकी सोसाइटी के कार्यक्रम और पास', phoneLabel: 'मोबाइल नंबर', sendOtp: 'OTP भेजें', invalidPhone: '10 अंकों का सही मोबाइल नंबर दर्ज करें',
    otpTitle: 'अपना नंबर सत्यापित करें', otpSent: 'हमने +91 {{phone}} पर 6 अंकों का कोड भेजा है', otpLabel: '6 अंकों का कोड', verify: 'सत्यापित करें',
    resend: 'कोड दोबारा भेजें', resendIn: '{{seconds}} सेकंड में दोबारा भेजें', invalidOtp: '6 अंकों का कोड दर्ज करें', yourName: 'हम आपको क्या कहकर बुलाएँ?',
    namePlaceholder: 'पूरा नाम',
  },
  onboarding: {
    title: 'स्वागत है{{name}}!', subtitle: 'अपनी सोसाइटी से जुड़ें या नई बनाएँ।', join: 'सोसाइटी से जुड़ें', joinSub: 'एडमिन से मिला इनवाइट कोड दर्ज करें',
    create: 'सोसाइटी बनाएँ', createSub: 'कार्यक्रम बनाएँ और पास बेचें', pendingTitle: 'स्वीकृति की प्रतीक्षा', signOut: 'साइन आउट',
  },
  join: {
    title: 'सोसाइटी से जुड़ें', codeLabel: 'इनवाइट कोड', scanQr: 'इनवाइट QR स्कैन करें', find: 'सोसाइटी खोजें', wing: 'विंग / ब्लॉक', flat: 'फ़्लैट नंबर',
    request: 'जुड़ने का अनुरोध भेजें', sent: 'अनुरोध भेज दिया गया! एडमिन जल्द ही देखेंगे।', invalidCode: 'इस कोड से कोई सोसाइटी नहीं मिली',
  },
  home: { upcoming: 'आगामी', past: 'पिछले', emptyUpcoming: 'कोई आगामी कार्यक्रम नहीं', soldOut: 'बिक चुका', closed: 'बुकिंग बंद', createEvent: 'नया कार्यक्रम' },
  event: { about: 'विवरण', venue: 'स्थान', when: 'कब', passes: 'पास', getPasses: 'पास लें', bookingClosed: 'बुकिंग बंद है', eventOver: 'कार्यक्रम समाप्त हो गया' },
  buy: { title: 'पास चुनें', qty: 'संख्या', holders: 'हर पास किसके लिए है?', holderName: 'नाम', member: 'निवासी', guest: 'मेहमान', total: 'कुल', continueToPay: 'भुगतान के लिए आगे बढ़ें' },
  order: {
    awaitingPayment: 'भुगतान की प्रतीक्षा', inReview: 'भुगतान की जाँच जारी है', approvedTitle: 'भुगतान स्वीकृत 🎉', payViaUpi: 'UPI ऐप से भुगतान करें',
    screenshot: 'भुगतान का स्क्रीनशॉट', pickScreenshot: 'स्क्रीनशॉट चुनें', utr: 'UTR / संदर्भ संख्या', submitProof: 'स्वीकृति के लिए जमा करें', viewPasses: 'मेरे पास देखें',
  },
  passes: { title: 'मेरे पास', empty: 'अभी कोई पास नहीं', offlineBanner: 'ऑफ़लाइन — फ़ोन में सहेजे पास दिख रहे हैं', showQr: 'गेट पर यह QR दिखाएँ', revoked: 'रद्द' },
  gallery: { title: 'गैलरी', empty: 'अभी कोई फ़ोटो नहीं', upload: 'फ़ोटो अपलोड करें' },
  scan: { title: 'पास स्कैन करें', allowed: 'प्रवेश की अनुमति', denied: 'प्रवेश न दें', scanned: 'स्कैन', sold: 'बिके', tapContinue: 'अगला स्कैन करने के लिए टैप करें' },
  manage: { title: 'प्रबंधन', approvals: 'भुगतान स्वीकृति', events: 'कार्यक्रम', members: 'सदस्य', reports: 'रिपोर्ट', invite: 'निवासियों को आमंत्रित करें', settings: 'सोसाइटी सेटिंग' },
  settings: { title: 'सेटिंग', language: 'भाषा', signOut: 'साइन आउट', name: 'नाम' },
};
export default hi;
