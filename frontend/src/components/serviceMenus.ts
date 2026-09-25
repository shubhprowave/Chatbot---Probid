/** Service quick menus (ported from the legacy widget).
 *  Level-1 services -> level-2 follow-up questions. Clicking a service shows
 *  its questions locally; clicking a question sends it as a normal chat message. */

export interface ServiceItem {
  key: string;
  label: string;
}

export interface SubMenu {
  prompt: string;
  items: string[];
}

export const SERVICES: ServiceItem[] = [
  { key: "gem", label: "🏛️ GeM Registration" },
  { key: "tender", label: "📑 Government Tender" },
  { key: "find", label: "🔍 Find Tenders" },
  { key: "bidding", label: "💼 Tender Bidding Assistance" },
  { key: "oem", label: "🏷️ OEM Panel Registration" },
  { key: "brand", label: "®️ Brand Approval" },
  { key: "listing", label: "🛒 GeM Product Listing" },
  { key: "pricing", label: "💰 Tender Pricing / BOQ" },
  { key: "docs", label: "📄 Documents Required" },
  { key: "expert", label: "📞 Talk to an Expert" },
];

export const SUB_MENUS: Record<string, SubMenu> = {
  gem: {
    prompt: "What do you want to know about GeM Registration?",
    items: [
      "How to register on GeM?",
      "What documents are required for GeM registration?",
      "How much does GeM registration cost?",
      "Can a new business register on GeM?",
      "How long does GeM registration take?",
      "Can I register on GeM without GST?",
      "Can ProBid register my business on GeM?",
      "I already have a GeM account. Can ProBid help me?",
    ],
  },
  tender: {
    prompt: "What do you need help with regarding Government Tenders?",
    items: [
      "How to find government tenders?",
      "How do I check tender eligibility?",
      "What documents are required for tender bidding?",
      "How do I submit a government tender?",
      "How should I prepare a BOQ?",
      "Why was my bid rejected?",
      "Can ProBid submit the tender for me?",
      "I want help with a tender",
    ],
  },
  find: {
    prompt: "What do you want to know about finding tenders?",
    items: [
      "Can you find tenders for my business?",
      "I want tenders for my product. What information should I provide?",
      "How to find government tenders?",
    ],
  },
  bidding: {
    prompt: "What do you need help with regarding Tender Bidding?",
    items: [
      "Can ProBid help me submit a tender?",
      "Why was my government tender rejected?",
      "How can I increase my chances of winning a tender?",
      "Can ProBid guarantee that I will win a tender?",
    ],
  },
  oem: {
    prompt: "What do you want to know about OEM Panel Registration?",
    items: [
      "What is OEM registration on GeM?",
      "How can I get OEM approval on GeM?",
      "Can a manufacturer get OEM approval on GeM?",
    ],
  },
  brand: {
    prompt: "What do you want to know about Brand Approval?",
    items: [
      "How can I add my brand to GeM?",
      "My brand is not available on GeM. What should I do?",
    ],
  },
  listing: {
    prompt: "What do you want to know about GeM Product Listing?",
    items: [
      "How can I list my product on GeM?",
      "Why is my product not getting approved on GeM?",
      "Can ProBid help with GeM product listing?",
    ],
  },
  pricing: {
    prompt: "What do you want to know about Tender Pricing / BOQ?",
    items: [
      "What is BOQ in a government tender?",
      "How should I decide my tender price?",
      "Can ProBid help prepare the BOQ?",
    ],
  },
  docs: {
    prompt: "Which documents do you want to know about?",
    items: [
      "What documents are required for GeM registration?",
      "What documents are required for government tender bidding?",
      "What documents should I keep ready before bidding?",
    ],
  },
  expert: {
    prompt: "How would you like to connect with our team?",
    items: [
      "I want to talk to someone from ProBid.",
      "I need urgent help with a tender. What should I do?",
      "What services does ProBid provide?",
      "How much does ProBid charge?",
    ],
  },
};
