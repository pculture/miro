<?php

$ignoreAgents = Array(
	'StarProse', // looks to be spamvertising
	'Referrer', // looks to be spamvertising
	'Advertising', // looks to be spamvertising
	'.WONKZ', // a new tag showing up, looks to be possible spammer
	'DB Browse', // guys building some new web system, pissed off a lot of folks
	'stokeybot', // looks to be spamvertising POPEX.com, no clue why.
	'LWP::Simple', // WORM!
	'lwp-trivial', // WORM!
);  

$ignoreReferSites = Array( 
	// us.
//	'localhost',
	
	// recent should be at the TOP.. -- lots of domains with emails @ support-4u.net seems to be spamming
	'ua-princeton.com', // same guy...
	'ficken-xxx.',
	'juris-net.',
	'e-holdem.',
	'mista-x.net',
	'credit-cards-zone.',
	'tomumberg2004.com',
	'texas-va-loan.',
	'threethreethree.org',
	'threethreethree.us',
	'op-clan.com',
	'doxycycline',
	'cephalexin',
	'lisinopril',
	'clomid',
	'crestor',
	'lipitor',
	'celexa',
	'zyprexa',
	'prilosec',
	'vioxx',
	'skin-care',
	'weight-loss',
	'-arthritis.',
		
	'sml338.org',
	'catalystmag.org',
	'queryguild.com',
	'phuketabacus.com',
	'qtw24.com',
	'buckhouston.com',
	'yourmorningshot.com',
	'myfriendstephanie.net',
	'newclassicalguitar.com',
	
	'weight-loss-',
	'diet-pill',
	'diet-supplement',
	'diet-patch',
	'-pharmacy',
	'pharmacy-',
	'e-pills-',
	'best-e-site.',
	'top-wins-2005.',
	
	'conjuratia.com',
	'vinhas.net',
	'win-in-poker.',
	'win-2005.',
	'wins-2005.',
	'buy-2005',
	'ca-america.com',
	'bnetsol.com',
	'registrarprice.com', // NS = bnetsol, support-24x7.biz
	'vrajitor.',
	'zindagi.us',
	'ro7kalbe.',
	'fearcrow.com',
	'vpshs.com',
	'ficken-live',
	'd4f.de',
	'wsop-', // 'world series of poker'... wsop is showing up all over.
	'wsop.',
	'.ws-op.',
	'samiuls.',
	'tiesearch.',
	'filthserver.',
	'covert-calls.',
	'printmyip.',
	'genaholincorporated.',
	'empirepoker.',
	'rohkalby.',

	'life-insurance',
	'student-loan',
	'credit-repair',
	'auto-loan',
	'car-loan',
	'car-laon',//sic
	'forex-trading',
	
	'propecia-',
	'propecia.',
	'phentermine-',
	'phentermine.',
	'levitra-',
	'levitra.',
	'viagra-',
	'viagra.',
	'cialis-',
	'cialis.',
	'bontril-',
	'bontril.',
	'xanax-',
	'xanax.',
	'meridia-',
	'meridia.',
	'valium-',
	'valium.',
	'ambien-',
	'ambien.',
	'prozac-',
	'prozac.',
	'tramadol-',
	'tramadol.',
	'smsportali.net',
	'6q.org',
	
	'vnsoul.org',
	'pisangrebus.',
	'eddiereva.',
	'ronnieazza.',
	'future-2000.net',
	'nutzu.com',
	'222222-4u.net',
	'4hs8.com',
	'38ha.com',
	
	'egygift.com',
	'e-poker-',
	'e-casino-',
	'casino-supply',
	'casino-directory',
	'atlantic-city-casino',
	'grand-casino',
	'progressive-slots',
	'-gambling',
	'internet-casino',
	'casino-games',
	'blackjack-',
	'blackjack.',
	'black-jack.',
	'musicbox1.com',
	'isacommie.com',
	'tigerspice.',

	'pissen.d4f.de',
	'aweblist.com',		
	'dvdsqueeze.com',
	
	'1stchoiceontv.',
	'highprofitclub.',
	'poker-',
	'-poker',

	'eddiereva.',
	'nutzu.',
	'-holdem',
	'englishapesattack',
	'dvdcopydecrypter',
	'florida-land-homes-sales',
	'domain-name-registration',
	'sexsearch',
	'adultaction',
	
	'doobu.com',
	'cash-advance',
	'advance-cash',
	'mortgage-',
	'-mortgage',
	'-payday-',
	'bad-credit',
	'home-loan',
	'refinance-',
	'interest-rate',
	'loan-calculator',
	
	'motherboard-finder-online',
	
	// these were some of the originals in the list -- I've left some in
/*
	'www.myelin.co.nz/ecosystem/bot.php', 
	'radio.xmlstoragesystem.com/rcsPublic/', 
	'blogdex.media.mit.edu//', 
	'subhonker6.userland.com/rcsPublic/', 
	'subhonker7.userland.com/rcsPublic/', 
	'FOAFBot 0.2', 
*/
	'popdex.com',
	'hornyhamster.com', 
	'XXXX:++++++++++', 
	'mastadonte.com' ,
	// newer things, but before I started tracking IPs
	'collegecamgirls.net',
	'em3.net',
	// by referring IP 64.239.138.76 -- colo3.hostcloud.com -- they should be notified, as many of these violate their hosting agreement terms (ie. p0rn), let alone via this spamming!
	'trafficfreaks.com', // hostcloud.com
	'necium.com', // hostcloud.com
	'sex4singles.com', // hostcloud.com
	'sexforsingles.com',
	'southwesternpokerplayer.com', // hostcloud.com
	'casino-gambling-pros.com',  // hostcloud.com
	'backlinks.seguru.net', // hostcloud.com
	'linkswhore.com', // hostcloud.com
	'fuckinglist.com',
	'local-underground.com',
	// by referring IP 193.255.207.252
	'live-home-webcams.blogspot.com',
	'buy-xenadrine.com',
	'pharmacygateway.com',
	'livehomewebcams.com',
	'collegecamgirls.com',
	// by referring IP 66.210.240.252
	'adult-models.biz',
	'busty2.com',
	'morganfinancialgroup.com', // alexocampo@spamcop.net webmaster?
	// by referring ip 65.160.98.31
	'onlinedatingchat.com',
	// 198.26.130.37
	'herbalecstacy.info',
	// 198.26.130.36
	'latin-goddess.com',
	// 66.98.224.39
	'pornwizzard.com',
	'babes.agenziadea.com',
	// 165.139.17.4
	'xxx.phuquall.com',
	//
	'linkstopussy.com',
	'capelinks.com',
	// 66.6.223.190
	'parishillton.com',
	'hopsports.com',
	// 211.152.14.93
	'sandysuesquiltshop.com',
	// 211.152.14.91
	'jiir.com', // some overseas website, totally spammed me via a bot.
	//
	'supadupazone.com',
	'paris-hilton-video.blogspot.com',
	'nudecelebblogs.com',
	'britneyspearsnude.blogspot.com',
	'gallerylisting.com',
	// 66.6.223.190
	'sex4singles.net',
	'electronictransfer.',
	'merchantaccount-creditcardprocessing.com',
	'best-merchant-accounts.com',
	'acceptcharges.com',
	'visa-mastercardservice.com',
	'cheap-merchant-services.com',
	'bexium.com',
	'fastcharge.com',
	//
	'sexsq.com',
	'freenudecelebrity.net',
	'my-fetishes.com',
	'latinablvd.com',
	//
	'poker-casino.skipme.com',
	'amateurxpass.com',
	'shatteredreality.net',
	'female-ejaculation-squirting.payshots.com',
	// 66.230.218.66, .67
	'sexer.com', // this is the ROOT site, all redirect to it generallt...
	'rotatingcunts.com',
	'whincer.net',
	'emedici.net',
	'ptporn.com',
	'sydneyhay.com',
	'adult-model-nude-pictures.com',
	'trottinbob.com',
	'engine-on-fire.com',
	'iconsofcorruption.com',
	'thiswillbeit.com',
	'zhaori-food.com',
	'runawayclicks.com',
	'laestacion101.com',
	'ptcgzone.com',
	'triacoach.net',
	'likewaterlikewind.com',
	'jesuislemonds.com',
	'clubstic.com',
	'asiadatingservices.com',
	'miltf.co.uk',
	'henrythehunk.com',
	'coolenabled.com',
	'bascom-solutions.com',
	'mastheadwankers.com',
	'onlinewithaline.com',
	'69-xxx.com',
	'miltf.co.uk',
	'swinger-party-free-dating-porn-sluts.com',
	'myhomephonenumber.com',
	'hotmatchup.co.uk',
	'laser-creations.com',
	'hotmatchup.co.uk',
	'free-xxx-pictures-porno-gallery.com',
	'monstermonkey.net',
	'marcofields.com',
	'delorentos.com',
	'cruisepatrol.co.uk',
	'szmjht.com',
	'tttframes.com',
	'onlinewithaline.com',
	'maki-e-pens.com',
	'peepingmoe.co.uk',
	'mercurybar.com',
	'fuck-michaelmoore.com',
	'unicornonero.com',
	'paginadeautor.com',
	
	// starting to snag some things from simon.incutio.com -- cleaned up HEAVILY!
	'a2z-casino.biz',
	'virginia-beach-hotels-discount-cheap-lodging-reservations.',
	'cheap-pills',
	'online-pharma',
	'onlinepharma',
	'pharmacies.',
	'diet-pills',
	'porn-4u.',
	// for these, I assume I can basically 'keyword filter' safely enough...
	'-enlargement',
	'e-order-',
	'penis-',
	'penis4pills',
	'-vigrx',
	'-vig-rx',
	
	'sex-video',
	// 208.62.160.32
	'christycanyon.biz',
	// same, later...
	'celeb-sex-tapes.com',
	'briana-bank.biz',
	// stupid. 172.197.161.95
	'admuncher.com',
	
	//new
	'hqsearch.net',
	
	//211.157.8.44
	'autodry.com', // Wow, COMMERCIAL spamming.
	
	// 69.50.191.130
	'7voyeur-upskirt.com',
	'taboosexsite.com',
	'incest-only.net',
	'scat-only.com',
	'rape-only.com',
	'xfreehosting.com',
	
	// spammer 64.255.163.85		
	'brokersaandpokers.com',
	'masteroftheblasterhill.com',
	'whitpagesrippers.com',
	'browserwindowcleaner.com',
	'newrealeasesonline.com',
	'realestateonthehill.net',
	'investment4cashiers.com',
	'fruitologist.net',
	'nextfrontiersonline.com',
	'booksandpages.com',
	'justanotherdomainname.com',
	'happychappywacky.com',
	'yuppieslovestocks.com',
	'midnightlaundries.com',
	'flowershopentertainment.com',
	'mykeyboardisbroken.com',
	'wordfilebooklets.com',
	'business2fun.com',
	'vinegarlemonshots.com',
	
	// not sure how this hit...
	'basemarketplace.com',
	
	// comment spammers specifically...
	// these two are the celebrex spammer.
	"taremociecall.com",
	"nabmlior.com",
	"glucophagepharmacy.com",
	// new jerk
	"freenetshopper.com",
	// and another
	"verybrowse.com",
	// more...
	"headachetreatment.net",
	"relievepain.org",
	"paxilmedication.biz",
	
	// ===== things that aren't really 'blacklisted', just 'shouldn't show up in referer list'
	// forum with no apparent links, has come up a few times now.
	// activated until I can find that they aren't spamming.   Haven't seen a valid referral yet.
	'popex.com',
	
	// I'm getting spam search/referer results off locators.com, shutting them down for now.
	'locators.com',
	
	// some new stuff from bill hayes
	'42tower.ws',
	'3333.ws',
	'glory-holes.blogspot.com',
	'trueuninstall.com',
	
	// comment spam -- shouldn't REALLY be nuked, as sometimes it's jerks being paid money to try
	// and increase site visits or pagerank, but...
	'stfc-isc.org',
	'vivlart.com',
	'lambethcouncil.com',
	'kyfarmhouse.org',
	's-sites.net',
	'redcentre.org',
	'lakesideartonline.com',
	'pages4people.com',
	'sydney-harbour.info',
	'mbgeezers.com',
	'nancyflowerswilson.com',
	'vtsae.org',
	'phrensy.org',
	'ottawavalleyag.org',
	'pasuquinio.com',
	'longslabofjoy.com',
	'nikkiwilliams.info',
	'uk-virtual-office-solutions.com',
	'valeofglamorganconservatives.org',
	'vivlart.com',
	'playandwin777.com',
	'kinggimp.org',
	'taliesinfellows.org',
	'workfromhome-homebasedbusiness.com',
	
	'poker-rooms-777',
	'texas-hold',
	
	// start of new for nov 04
	'home-equity-loan', 
	'.bucuo.net',
	'.movsea.com',
	'.8cuo.net',
	'paydayloans.',
	'credit-report',
	'online-dating',
	'online-casino',
	'casino-on',
	'online-poker',
	'poker-on',
	'online-gaming',
	'free-online',
	'online-slot',
	'slot-machine',
	'free-slot',
	'line-slot', // online-slot, multi-line-slots,...
	'party-poker',
	'video-poker',
	'poker-games',
	'no-download-',
	'free-casino',
	'vegas-casino',
	'direct-tv-',
	'cashadvance',
	'faxless-payday',
	'payday-advance',
	'loans-no-fax.com',
	
	'mortgage-rates',
	'.uaeecommerce.com',
	'debt-help',
	'bill-consolidation',
	'fidelityfunding.net',
	
	// all one guy
	'canadianlabels.net',
	'8gold.com',
	'onlinegamingassociation.com',
	
	// new, might already be closed accts...
	'teambeck.org',
	'middlecay.org',
	'hasslerenterprises.org',
	'reservedining.net',
	'mcdortaklar.com',
	'paramountseedfarms.net',
	
	'credit-card',
	'debt-consolidation',
	'insurance-quote',
	
	'tecrep-inc.',
	'cheat-elite.',
	'rulo.biz',
	
	// referrer spammer
	'nixnix.biz',
	'.gb.com', //new referrer spam
	
    // end of list
    'thisissomethingthatwillnevermatchawebsite.no'
); 


$ignoreSpammerIPs = Array(
/*
		'127.0.0.1',
		'192.168.0.1',
		'192.168.1.1',
		'192.168.0.100',
		'192.168.1.100',
		'192.168.0.101',
		'192.168.1.101',
*/
	// long time spam address, now showing up as referring domain.
	'12.163.72.13',
	
	// STILL VERIFIED ACTIVE
	'69.50.191.130',

	// these are specifically blocking the worst offenders above directly by IP address...
/*
    '64.239.138.76',
    '193.255.207.252',
    '66.210.240.252',
    // merchant card guys
	'66.6.223.190',
    "62.219.59.122", // guy spamming with celebrex links.
	// porn spam.. ouch.
	'66.230.218.66',
	'66.230.218.67',
	'208.62.160.32',
	// spammed with multiple sites.
	'64.255.163.85'
*/
);

?>