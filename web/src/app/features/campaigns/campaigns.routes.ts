import { Routes } from '@angular/router';

import { CampaignDetailPage } from './pages/campaign-detail/campaign-detail.page';
import { CampaignListPage } from './pages/campaign-list/campaign-list.page';

export const CAMPAIGN_ROUTES: Routes = [
  { path: '', component: CampaignListPage },
  { path: ':campaignId', component: CampaignDetailPage },
];
