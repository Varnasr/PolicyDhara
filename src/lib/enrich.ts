/**
 * Policy Knowledge Enrichment
 * Maps sectors and types to structured knowledge: ministries, stakeholders,
 * affected populations, and political spectrum positioning.
 */

export interface PolicyEnrichment {
  ministries: string[];
  stakeholders: string[];
  affectedPopulation: string;
  politicalLean: number; // -2 (Left) to +2 (Right), 0 = Centre
  politicalLabel: string;
  governmentEra: string;
  governingParty: string;
  keyNumbers: string[];
}

const SECTOR_MINISTRIES: Record<string, string[]> = {
  'Education': ['Ministry of Education', 'UGC', 'AICTE'],
  'Health': ['Ministry of Health & Family Welfare', 'ICMR', 'Ministry of Ayush'],
  'Finance & Economy': ['Ministry of Finance', 'RBI', 'SEBI', 'DEA'],
  'Agriculture': ['Ministry of Agriculture & Farmers Welfare', 'ICAR', 'Ministry of Consumer Affairs, Food & Public Distribution (FCI)'],
  'Digital & Technology': ['Ministry of Electronics & IT', 'TRAI', 'CERT-In'],
  'Defence & Security': ['Ministry of Defence', 'Ministry of Home Affairs', 'NSA'],
  'Climate & Environment': ['Ministry of Environment, Forest & Climate Change', 'CPCB'],
  'Energy': ['Ministry of Power', 'Ministry of New & Renewable Energy', 'CEA'],
  'Labour & Employment': ['Ministry of Labour & Employment', 'EPFO', 'ESIC'],
  'Social Protection': ['Ministry of Social Justice & Empowerment', 'NITI Aayog'],
  'Governance & Reform': ['PMO', 'Cabinet Secretariat', 'DARPG', 'NITI Aayog'],
  'Transport & Infrastructure': ['Ministry of Road Transport & Highways', 'Ministry of Railways', 'NHAI'],
  'Rural Development': ['Ministry of Rural Development', 'Ministry of Panchayati Raj'],
  'Urban Development': ['Ministry of Housing & Urban Affairs', 'Smart Cities Mission'],
  'Trade & Commerce': ['Ministry of Commerce & Industry', 'DPIIT', 'DGFT'],
  'Water & Sanitation': ['Ministry of Jal Shakti', 'CGWB'],
  'Housing': ['Ministry of Housing & Urban Affairs', 'NHB'],
  'Child Rights & Youth': ['Ministry of Women & Child Development', 'NCPCR', 'Ministry of Youth Affairs & Sports'],
  'Gender & Women': ['Ministry of Women & Child Development', 'NCW'],
  'Tribal & Indigenous': ['Ministry of Tribal Affairs', 'NCST'],
  'Disability & Inclusion': ['Department of Empowerment of Persons with Disabilities', 'Ministry of Social Justice & Empowerment', 'Office of the Chief Commissioner for Persons with Disabilities'],
  'Science & Innovation': ['Ministry of Science & Technology', 'DST', 'CSIR', 'Department of Space (ISRO)'],
  'Civil Liberties': ['Ministry of Home Affairs', 'Ministry of Law & Justice', 'NHRC', 'Supreme Court of India', 'State Human Rights Commissions'],
};

const SECTOR_STAKEHOLDERS: Record<string, string[]> = {
  'Education': ['Students', 'Teachers & Faculty', 'Universities', 'State Education Boards', 'EdTech Industry', 'Parents'],
  'Health': ['Patients', 'Healthcare Workers', 'Hospitals & Clinics', 'Pharma Industry', 'Insurance Providers', 'ASHA Workers'],
  'Finance & Economy': ['Taxpayers', 'Banks & NBFCs', 'Investors', 'MSMEs', 'Stock Markets'],
  'Agriculture': ['Farmers', 'FPOs', 'Agri-Input Industry', 'APMC Markets', 'Food Processing Units'],
  'Digital & Technology': ['Internet Users', 'Tech Companies', 'Startups', 'Telecom Providers', 'Data Processors'],
  'Defence & Security': ['Armed Forces', 'Defence PSUs', 'Border Communities', 'Veterans', 'Defence Industry'],
  'Climate & Environment': ['Forest Communities', 'Polluting Industries', 'Renewable Energy Firms', 'Wildlife', 'Coastal Populations'],
  'Energy': ['Power Consumers', 'DISCOMs', 'Coal Industry', 'Solar/Wind Developers', 'State Electricity Boards'],
  'Labour & Employment': ['Workers', 'Trade Unions', 'Employers', 'Gig Workers', 'Migrant Labour'],
  'Social Protection': ['BPL Families', 'Senior Citizens', 'Persons with Disabilities', 'Unorganised Workers'],
  'Governance & Reform': ['Civil Servants', 'State Governments', 'Judiciary', 'Citizens', 'RTI Activists'],
  'Transport & Infrastructure': ['Commuters', 'Trucking Industry', 'Railways Employees', 'Construction Sector', 'Toll Operators'],
  'Rural Development': ['Rural Households', 'Gram Panchayats', 'SHGs', 'Rural Employment Guarantee Workers'],
  'Urban Development': ['Urban Residents', 'Municipal Corporations', 'Real Estate Developers', 'Slum Dwellers'],
  'Trade & Commerce': ['Exporters', 'Importers', 'MSMEs', 'FDI Investors', 'Customs & GST Payers'],
  'Water & Sanitation': ['Rural Households', 'Urban Water Utilities', 'Farmers (Irrigation)', 'Sanitation Workers'],
  'Housing': ['Homebuyers', 'Real Estate Developers', 'Slum Dwellers', 'Housing Finance Companies'],
  'Child Rights & Youth': ['Children', 'Adolescents', 'Anganwadi Workers', 'Juvenile Justice System', 'Youth Organisations'],
  'Gender & Women': ['Women', 'SHGs', 'Women Entrepreneurs', 'Domestic Workers', 'Gender Minorities'],
  'Tribal & Indigenous': ['Scheduled Tribes', 'Forest Dwellers', 'Tribal Cooperatives', 'Fifth Schedule Areas'],
  'Disability & Inclusion': ['Persons with Disabilities', 'Disability Rights Organisations', 'Special Educators', 'Rehabilitation Professionals', 'Caregivers'],
  'Science & Innovation': ['Researchers', 'R&D Institutions', 'Startups', 'Patent Holders', 'Universities'],
  'Civil Liberties': ['Citizens', 'Human Rights Defenders', 'Media & Press', 'Minorities', 'Prisoners & Detainees', 'Protestors', 'Legal Aid Recipients'],
};

const SECTOR_AFFECTED: Record<string, string> = {
  'Education': '~350 million students, 10 million teachers',
  'Health': '1.4 billion citizens, 5 million healthcare workers',
  'Finance & Economy': '1.4 billion citizens, 63 million MSMEs',
  'Agriculture': 'Farming households and agricultural workers',
  'Digital & Technology': 'Internet users, technology firms and startups',
  'Defence & Security': '1.4 million active military, border populations',
  'Climate & Environment': 'All citizens, forest-dependent communities',
  'Energy': '1.4 billion electricity consumers',
  'Labour & Employment': 'Workers in the formal and informal sectors',
  'Social Protection': 'Poor and vulnerable households, senior citizens',
  'Governance & Reform': '1.4 billion citizens, 20 million government employees',
  'Transport & Infrastructure': 'All citizens, 8 million truck operators',
  'Rural Development': '~900 million rural population, 250,000 gram panchayats',
  'Urban Development': '~500 million urban residents, 8,000+ cities/towns',
  'Trade & Commerce': '63 million MSMEs, export-import community',
  'Water & Sanitation': 'Rural and urban households that depend on public water and sanitation services',
  'Housing': 'Urban and rural households without adequate housing',
  'Child Rights & Youth': 'Children under 18 and young people',
  'Gender & Women': 'Women and girls of all ages',
  'Tribal & Indigenous': '~104 million Scheduled Tribe population, 8.6% of India (Census 2011)',
  'Disability & Inclusion': '~26.8 million persons with disabilities (Census 2011; likely undercounted)',
  'Science & Innovation': '~1 million researchers, R&D ecosystem',
  'Civil Liberties': '1.4 billion citizens, minorities, undertrials, press freedom',
};

const SECTOR_KEY_NUMBERS: Record<string, string[]> = {
  'Education': ['Ministry of Education budget: Rs 1,28,650 crore (Budget Estimate 2025-26)', 'NEP 2020 target: 50% gross enrolment ratio in higher education by 2035'],
  'Health': ['Ministry of Health and Family Welfare budget: Rs 99,859 crore (Budget Estimate 2025-26)', 'Ayushman Bharat PM-JAY: health cover of Rs 5 lakh for 12 crore families'],
  'Finance & Economy': ['Fiscal deficit target: 4.3% of GDP (Budget Estimate 2026-27)', 'Union expenditure: Rs 53,47,315 crore (Budget Estimate 2026-27)'],
  'Agriculture': ['Agriculture, farmers welfare, research and education budget: Rs 1,40,529 crore (Budget Estimate 2026-27)', 'PM-KISAN: Rs 6,000 a year in income support to farmer families'],
  'Digital & Technology': ['UPI: 24.07 billion transactions in September 2026 (NPCI)'],
  'Defence & Security': ['Ministry of Defence budget: Rs 7.85 lakh crore (Budget Estimate 2026-27)', '1.4 million active military personnel'],
  'Climate & Environment': ['Net-zero target: 2070', 'Non-fossil capacity: 300.50 GW, over 54% of installed capacity (31 July 2026)'],
  'Energy': ['500 GW non-fossil fuel capacity target by 2030', 'Renewable capacity including large hydro: 274.68 GW (31 March 2026)'],
  'Labour & Employment': ['Four Labour Codes in force since 21 November 2025, replacing 29 central labour laws'],
  'Social Protection': ['Ayushman Bharat PM-JAY: health cover of Rs 5 lakh for 12 crore families', 'MGNREGA repealed on 1 July 2026 and replaced by the VB-G RAM G Act, 2025'],
  'Governance & Reform': ['20 million central + state government employees'],
  'Transport & Infrastructure': ['Union capital expenditure: Rs 12.2 lakh crore (Budget Estimate 2026-27)'],
  'Rural Development': ['PMGSY: 7.25 lakh km rural roads', 'SHG network: 9 crore women members'],
  'Urban Development': ['Metro rail: 900+ km operational'],
  'Trade & Commerce': [],
  'Water & Sanitation': ['SBM 2.0: Rs 1.4 lakh crore outlay'],
  'Housing': [],
  'Child Rights & Youth': [],
  'Gender & Women': ['Maternity benefit: Rs 5,000 under PMMVY'],
  'Tribal & Indigenous': ['Scheduled Tribe development: Rs 14,926 crore across ministries (Budget Estimate 2025-26)'],
  'Disability & Inclusion': ['RPwD Act 2016: 21 recognised disabilities'],
  'Science & Innovation': ['Global Innovation Index 2026: India ranks 38th of 139 economies'],
  'Civil Liberties': ['Internet shutdowns in 2024: India 84, second to Myanmar 85 (Access Now)'],
};

/**
 * Government eras — political lean is based on the governing coalition,
 * not the policy sector. The lean is a rough editorial label for the governing
 * coalition, not a measure of any policy. Era dates are the swearing-in dates of
 * the Prime Minister. "NDA I, II, III" here means the Modi governments of 2014,
 * 2019 and 2024, not the Vajpayee NDA of 1998 to 2004. India's central
 * government trajectory:
 *
 * UPA I  (May 2004 – May 2009):  Congress-led, with outside support from the Left Front until July 2008 → Centre-Left
 * UPA II (May 2009 – May 2014):  Congress-led                → Centre to Centre-Left
 * NDA I  (May 2014 – May 2019):  BJP majority                → Centre-Right to Right
 * NDA II (May 2019 – Jun 2024):  BJP strong majority          → Right
 * NDA III (Jun 2024 – present):  BJP-led coalition            → Centre-Right to Right
 */
interface GovEra {
  name: string;
  party: string;
  lean: number;  // -2 to +2
  label: string;
  start: string; // YYYY-MM-DD
  end: string;   // YYYY-MM-DD or '9999-12-31' for current
}

const GOV_ERAS: GovEra[] = [
  { name: 'UPA I',   party: 'Congress-led UPA',  lean: -1, label: 'Centre-Left',  start: '2004-05-22', end: '2009-05-21' },
  { name: 'UPA II',  party: 'Congress-led UPA',  lean: -1, label: 'Centre-Left',  start: '2009-05-22', end: '2014-05-25' },
  { name: 'NDA I',   party: 'BJP-led NDA',       lean: 1,  label: 'Centre-Right', start: '2014-05-26', end: '2019-05-29' },
  { name: 'NDA II',  party: 'BJP-led NDA',       lean: 2,  label: 'Right',        start: '2019-05-30', end: '2024-06-08' },
  { name: 'NDA III', party: 'BJP-led NDA',       lean: 1,  label: 'Centre-Right', start: '2024-06-09', end: '9999-12-31' },
];

function getGovernmentEra(date: string): GovEra {
  const d = date || '2025-01-01';
  for (const era of GOV_ERAS) {
    if (d >= era.start && d <= era.end) return era;
  }
  // Default to current era for undated policies
  return GOV_ERAS[GOV_ERAS.length - 1];
}

export function enrichPolicy(sectors: string[], type: string, date?: string): PolicyEnrichment {
  // Aggregate ministries and stakeholders from all sectors
  const ministrySet = new Set<string>();
  const stakeholderSet = new Set<string>();
  const keyNumbers: string[] = [];
  let affectedPopulation = '—';

  for (const s of sectors) {
    const ministries = SECTOR_MINISTRIES[s] || [];
    ministries.forEach(m => ministrySet.add(m));

    const stakeholders = SECTOR_STAKEHOLDERS[s] || [];
    stakeholders.slice(0, 3).forEach(st => stakeholderSet.add(st));

    if (affectedPopulation === '—' && SECTOR_AFFECTED[s]) {
      affectedPopulation = SECTOR_AFFECTED[s];
    }

    // Collect distinct key numbers from all sectors
    const nums = SECTOR_KEY_NUMBERS[s] || [];
    for (const n of nums) {
      if (!keyNumbers.includes(n)) keyNumbers.push(n);
    }
  }

  // Political lean is based on the governing coalition at the time
  const era = getGovernmentEra(date || '');

  return {
    ministries: Array.from(ministrySet).slice(0, 5),
    stakeholders: Array.from(stakeholderSet).slice(0, 6),
    affectedPopulation,
    politicalLean: era.lean,
    politicalLabel: era.label,
    governmentEra: era.name,
    governingParty: era.party,
    keyNumbers: keyNumbers.slice(0, 4),
  };
}
