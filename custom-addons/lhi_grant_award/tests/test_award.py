# -*- coding: utf-8 -*-
from odoo.tests import common

class TestLhiGrantAward(common.TransactionCase):
    
    def test_award_extension(self):
        """ Test award creation with new extension fields """
        donor = self.env['lhi.donor'].create({
            'name': 'Award Donor',
            'code': 'AD-001',
            'donor_type': 'ngo'
        })
        
        funding_source = self.env['lhi.funding.source'].create({
            'name': 'Test Source',
            'code': 'TS-001'
        })
        
        award = self.env['lhi.award'].create({
            'name': 'Test Award',
            'funding_source_id': funding_source.id,
            'donor_id': donor.id,
            'closeout_period_days': 60
        })
        
        self.assertEqual(award.donor_id.id, donor.id)
        self.assertEqual(award.closeout_period_days, 60)
