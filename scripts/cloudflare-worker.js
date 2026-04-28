/**
 * Cloudflare Worker: PagerDuty On-Call Proxy
 *
 * Deployment:
 * 1. Go to https://dash.cloudflare.com/
 * 2. Workers & Pages > Create Worker
 * 3. Name it: team-oncall
 * 4. Paste this code
 * 5. Settings > Variables > Add:
 *    - PAGERDUTY_API_KEY: your PagerDuty API key (read-only is fine)
 * 6. Deploy
 *
 * The worker will be available at: https://team-oncall.<your-subdomain>.workers.dev
 * Update ONCALL_API_URL in index.html to match your worker URL.
 */

export default {
  async fetch(request, env) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const teamId = url.searchParams.get('teamId');

    if (!teamId) {
      return new Response(JSON.stringify({ error: 'teamId required' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    try {
      const now = new Date().toISOString();
      const pdUrl = `https://api.pagerduty.com/oncalls?time_zone=UTC&since=${now}&until=${now}&schedule_ids=[]&escalation_policy_ids=[]&include[]=users`;

      const schedulesResponse = await fetch(
        `https://api.pagerduty.com/schedules?team_ids[]=${teamId}`,
        {
          headers: {
            'Authorization': `Token token=${env.PAGERDUTY_API_KEY}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!schedulesResponse.ok) {
        throw new Error(`PagerDuty schedules API error: ${schedulesResponse.status}`);
      }

      const schedulesData = await schedulesResponse.json();
      const schedules = schedulesData.schedules || [];

      let primary = null;
      let secondary = null;

      for (const schedule of schedules) {
        const oncallResponse = await fetch(
          `https://api.pagerduty.com/oncalls?schedule_ids[]=${schedule.id}&since=${now}&until=${now}`,
          {
            headers: {
              'Authorization': `Token token=${env.PAGERDUTY_API_KEY}`,
              'Content-Type': 'application/json'
            }
          }
        );

        if (oncallResponse.ok) {
          const oncallData = await oncallResponse.json();
          const oncalls = oncallData.oncalls || [];

          for (const oncall of oncalls) {
            const name = oncall.user?.summary || oncall.user?.name;
            const level = oncall.escalation_level;
            const scheduleName = schedule.name.toLowerCase();

            if (scheduleName.includes('primary') || level === 1) {
              if (!primary) primary = name;
            } else if (scheduleName.includes('secondary') || level === 2) {
              if (!secondary) secondary = name;
            } else if (!primary) {
              primary = name;
            }
          }
        }
      }

      return new Response(JSON.stringify({ primary, secondary }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  }
};
