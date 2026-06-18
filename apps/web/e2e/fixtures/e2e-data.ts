export const E2E = {
  campaignId: 'campaign_e2e',
  campaignTitle: 'Campagne E2E',
  documentId: 'doc_e2e',
  documentFilename: 'aventure-e2e.pdf',
  sections: {
    intro: 'sec_intro',
    ch1: 'sec_ch1',
    annex: 'sec_annex',
  },
  chunks: {
    intro: 'chunk_intro',
    ch1: 'chunk_ch1',
    ch1b: 'chunk_ch1b',
  },
  statBlocks: {
    gobelin: 'Gobelin',
    orc: 'Orc',
    gobelinChunkId: 'chunk_stat_gobelin',
    orcChunkId: 'chunk_stat_orc',
  },
} as const;
