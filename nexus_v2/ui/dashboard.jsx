import React, { useState } from 'react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';

const revenueData = [
  { year: 'Year 1', revenue: 0.85, expenses: 0.48, netIncome: 0.37, margin: 43.5 },
  { year: 'Year 2', revenue: 11.26, expenses: 5.64, netIncome: 5.62, margin: 50.0 },
  { year: 'Year 3', revenue: 64.41, expenses: 29.66, netIncome: 34.75, margin: 54.0 },
  { year: 'Year 4', revenue: 201.13, expenses: 90.51, netIncome: 110.62, margin: 55.0 },
  { year: 'Year 5', revenue: 454.37, expenses: 190.84, netIncome: 263.54, margin: 58.0 },
];

const revenueStreamsY5 = [
  { name: 'Consumer Hardware', value: 208.6, color: '#3B82F6' },
  { name: 'B2C App Subs', value: 83.88, color: '#10B981' },
  { name: 'Pre-Grading', value: 52.0, color: '#F59E0B' },
  { name: 'Marketplace', value: 45.0, color: '#EF4444' },
  { name: 'Hardware Rentals', value: 26.35, color: '#8B5CF6' },
  { name: 'B2B Subs', value: 19.14, color: '#EC4899' },
  { name: 'Other', value: 19.4, color: '#6B7280' },
];

const preGradingData = [
  { year: 'Year 1', cards: 0.05, revenue: 0.08 },
  { year: 'Year 2', cards: 0.5, revenue: 0.78 },
  { year: 'Year 3', cards: 5, revenue: 5.35 },
  { year: 'Year 4', cards: 15, revenue: 18.5 },
  { year: 'Year 5', cards: 40, revenue: 52 },
];

const customerData = [
  { year: 'Year 1', b2bShops: 100, b2cUsers: 10, hardwareUnits: 0 },
  { year: 'Year 2', b2bShops: 500, b2cUsers: 100, hardwareUnits: 50 },
  { year: 'Year 3', b2bShops: 2000, b2cUsers: 500, hardwareUnits: 350 },
  { year: 'Year 4', b2bShops: 5000, b2cUsers: 1000, hardwareUnits: 1350 },
  { year: 'Year 5', b2bShops: 10000, b2cUsers: 2000, hardwareUnits: 3350 },
];

const valuationData = [
  { year: 'Year 1', valuation: 6.8 },
  { year: 'Year 2', valuation: 135 },
  { year: 'Year 3', valuation: 966 },
  { year: 'Year 4', valuation: 2400 },
  { year: 'Year 5', valuation: 4500 },
];

const subscriptionTiers = [
  { tier: 'FREE', monthly: '$0', games: '1', preGrades: '5/mo', target: 'Hobbyists' },
  { tier: 'STARTER', monthly: '$29', games: '1', preGrades: '50/mo', target: 'Small Shops' },
  { tier: 'DEALER', monthly: '$79', games: '3', preGrades: '250/mo', target: 'Medium Shops' },
  { tier: 'PRO SHOP', monthly: '$149', games: 'ALL', preGrades: '1,000/mo', target: 'Large Shops' },
  { tier: 'ENTERPRISE', monthly: '$399', games: 'ALL', preGrades: '5,000/mo', target: 'Chains' },
];

export default function NexusDashboard() {
  const [activeTab, setActiveTab] = useState('overview');

  const formatCurrency = (value) => `$${value}M`;
  const formatLargeCurrency = (value) => value >= 1000 ? `$${(value/1000).toFixed(1)}B` : `$${value}M`;

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            NEXUS 5-YEAR FINANCIAL ANALYSIS
          </h1>
          <p className="text-gray-400 mt-2">Integrated Pre-Grading + Multi-Game Subscription Model</p>
        </div>

        {/* Key Metrics Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-xl p-4">
            <p className="text-blue-200 text-sm">Year 5 Revenue</p>
            <p className="text-3xl font-bold">$454M</p>
            <p className="text-blue-300 text-sm">↑ 536x from Y1</p>
          </div>
          <div className="bg-gradient-to-br from-green-600 to-green-800 rounded-xl p-4">
            <p className="text-green-200 text-sm">Year 5 Net Income</p>
            <p className="text-3xl font-bold">$264M</p>
            <p className="text-green-300 text-sm">58% margin</p>
          </div>
          <div className="bg-gradient-to-br from-purple-600 to-purple-800 rounded-xl p-4">
            <p className="text-purple-200 text-sm">Year 5 Valuation</p>
            <p className="text-3xl font-bold">$4.5B</p>
            <p className="text-purple-300 text-sm">10x revenue</p>
          </div>
          <div className="bg-gradient-to-br from-amber-600 to-amber-800 rounded-xl p-4">
            <p className="text-amber-200 text-sm">Pre-Grading Revenue</p>
            <p className="text-3xl font-bold">$52M</p>
            <p className="text-amber-300 text-sm">40M cards/year</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {['overview', 'pre-grading', 'customers', 'subscriptions', 'valuation'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                activeTab === tab 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1).replace('-', ' ')}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-gray-800 rounded-xl p-6">
          {activeTab === 'overview' && (
            <div className="space-y-8">
              <div>
                <h3 className="text-xl font-semibold mb-4">Revenue & Profitability Growth</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={revenueData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="year" stroke="#9CA3AF" />
                    <YAxis stroke="#9CA3AF" tickFormatter={(v) => `$${v}M`} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1F2937', border: 'none' }}
                      formatter={(value) => [`$${value}M`, '']}
                    />
                    <Legend />
                    <Area type="monotone" dataKey="revenue" stackId="1" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.6} name="Revenue" />
                    <Area type="monotone" dataKey="netIncome" stackId="2" stroke="#10B981" fill="#10B981" fillOpacity={0.6} name="Net Income" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-xl font-semibold mb-4">Year 5 Revenue Mix</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={revenueStreamsY5}
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        dataKey="value"
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                        labelLine={false}
                      >
                        {revenueStreamsY5.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => `$${value}M`} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div>
                  <h3 className="text-xl font-semibold mb-4">Profit Margin Expansion</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={revenueData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="year" stroke="#9CA3AF" />
                      <YAxis stroke="#9CA3AF" tickFormatter={(v) => `${v}%`} domain={[40, 60]} />
                      <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none' }} />
                      <Line type="monotone" dataKey="margin" stroke="#F59E0B" strokeWidth={3} dot={{ fill: '#F59E0B' }} name="Net Margin %" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'pre-grading' && (
            <div className="space-y-8">
              <div className="grid md:grid-cols-3 gap-4 mb-6">
                <div className="bg-gray-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm">5-Year Pre-Grading Revenue</p>
                  <p className="text-2xl font-bold text-amber-400">$76.7M</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm">Year 5 Cards Pre-Graded</p>
                  <p className="text-2xl font-bold text-blue-400">40M cards</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm">Avg Revenue Per Card</p>
                  <p className="text-2xl font-bold text-green-400">$1.30</p>
                </div>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-4">Pre-Grading Volume & Revenue</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={preGradingData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="year" stroke="#9CA3AF" />
                    <YAxis yAxisId="left" stroke="#9CA3AF" tickFormatter={(v) => `${v}M`} />
                    <YAxis yAxisId="right" orientation="right" stroke="#9CA3AF" tickFormatter={(v) => `$${v}M`} />
                    <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none' }} />
                    <Legend />
                    <Bar yAxisId="left" dataKey="cards" fill="#3B82F6" name="Cards (Millions)" />
                    <Bar yAxisId="right" dataKey="revenue" fill="#F59E0B" name="Revenue ($M)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-gray-700 rounded-lg p-4">
                <h4 className="font-semibold mb-3">Pre-Grading Service Pricing</h4>
                <div className="grid md:grid-cols-3 gap-4 text-sm">
                  <div className="bg-gray-800 rounded p-3">
                    <p className="text-gray-400">Quick Scan</p>
                    <p className="text-lg font-bold">$0.50</p>
                    <p className="text-gray-500">AI grade 1-10</p>
                  </div>
                  <div className="bg-gray-800 rounded p-3">
                    <p className="text-gray-400">Detailed Report</p>
                    <p className="text-lg font-bold">$2.00</p>
                    <p className="text-gray-500">Component scores + defects</p>
                  </div>
                  <div className="bg-gray-800 rounded p-3">
                    <p className="text-gray-400">Pre-Submit Analysis</p>
                    <p className="text-lg font-bold">$15.00</p>
                    <p className="text-gray-500">PSA/BGS prediction + ROI</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'customers' && (
            <div className="space-y-8">
              <div>
                <h3 className="text-xl font-semibold mb-4">Customer Growth</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={customerData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="year" stroke="#9CA3AF" />
                    <YAxis stroke="#9CA3AF" tickFormatter={(v) => v >= 1000 ? `${v/1000}K` : v} />
                    <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: 'none' }} />
                    <Legend />
                    <Line type="monotone" dataKey="b2bShops" stroke="#3B82F6" strokeWidth={2} name="B2B Shops" />
                    <Line type="monotone" dataKey="b2cUsers" stroke="#10B981" strokeWidth={2} name="B2C Users (K)" />
                    <Line type="monotone" dataKey="hardwareUnits" stroke="#F59E0B" strokeWidth={2} name="Hardware (K units)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="grid md:grid-cols-4 gap-4">
                <div className="bg-gray-700 rounded-lg p-4 text-center">
                  <p className="text-gray-400 text-sm">Year 5 B2B Shops</p>
                  <p className="text-3xl font-bold text-blue-400">10,000</p>
                  <p className="text-gray-500 text-sm">20% of global market</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-4 text-center">
                  <p className="text-gray-400 text-sm">Year 5 B2C Users</p>
                  <p className="text-3xl font-bold text-green-400">2M</p>
                  <p className="text-gray-500 text-sm">900K paid subscribers</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-4 text-center">
                  <p className="text-gray-400 text-sm">Hardware Sold</p>
                  <p className="text-3xl font-bold text-amber-400">3.35M</p>
                  <p className="text-gray-500 text-sm">Cumulative units</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-4 text-center">
                  <p className="text-gray-400 text-sm">Marketplace GMV</p>
                  <p className="text-3xl font-bold text-purple-400">$750M</p>
                  <p className="text-gray-500 text-sm">6% take rate = $45M</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'subscriptions' && (
            <div className="space-y-6">
              <h3 className="text-xl font-semibold">B2B Subscription Tiers (with Pre-Grading)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left py-3 px-4">Tier</th>
                      <th className="text-left py-3 px-4">Monthly</th>
                      <th className="text-left py-3 px-4">Games</th>
                      <th className="text-left py-3 px-4">Pre-Grades</th>
                      <th className="text-left py-3 px-4">Target</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subscriptionTiers.map((tier, idx) => (
                      <tr key={idx} className="border-b border-gray-700 hover:bg-gray-700">
                        <td className="py-3 px-4 font-semibold text-blue-400">{tier.tier}</td>
                        <td className="py-3 px-4">{tier.monthly}</td>
                        <td className="py-3 px-4">{tier.games}</td>
                        <td className="py-3 px-4">{tier.preGrades}</td>
                        <td className="py-3 px-4 text-gray-400">{tier.target}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="bg-gray-700 rounded-lg p-4 mt-6">
                <h4 className="font-semibold mb-3">Unit Economics</h4>
                <div className="grid md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-gray-400">B2B Enterprise LTV</p>
                    <p className="text-xl font-bold">$19,950</p>
                    <p className="text-green-400">LTV:CAC = 20x</p>
                  </div>
                  <div>
                    <p className="text-gray-400">B2C Pro LTV</p>
                    <p className="text-xl font-bold">$167</p>
                    <p className="text-green-400">LTV:CAC = 8.3x</p>
                  </div>
                  <div>
                    <p className="text-gray-400">Hardware Margin</p>
                    <p className="text-xl font-bold">70%</p>
                    <p className="text-green-400">$104 per unit</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'valuation' && (
            <div className="space-y-8">
              <div>
                <h3 className="text-xl font-semibold mb-4">Valuation Trajectory</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={valuationData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="year" stroke="#9CA3AF" />
                    <YAxis stroke="#9CA3AF" tickFormatter={(v) => v >= 1000 ? `$${v/1000}B` : `$${v}M`} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1F2937', border: 'none' }}
                      formatter={(value) => [value >= 1000 ? `$${(value/1000).toFixed(1)}B` : `$${value}M`, 'Valuation']}
                    />
                    <Area type="monotone" dataKey="valuation" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.6} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                <div className="bg-gray-700 rounded-lg p-4">
                  <h4 className="font-semibold mb-3">Funding Roadmap</h4>
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between">
                      <span>Seed (Now)</span>
                      <span className="font-bold">$500K</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Series A (Y2)</span>
                      <span className="font-bold">$10M</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Series B (Y3)</span>
                      <span className="font-bold">$50M</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Series C (Y4)</span>
                      <span className="font-bold">$100M</span>
                    </div>
                    <div className="flex justify-between">
                      <span>IPO (Y5)</span>
                      <span className="font-bold">$200M+</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-700 rounded-lg p-4">
                  <h4 className="font-semibold mb-3">Founder Equity Value</h4>
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between">
                      <span>Post-Seed (80%)</span>
                      <span className="font-bold">$2M</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Post-Series A (71%)</span>
                      <span className="font-bold">$63.9M</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Post-Series B (65%)</span>
                      <span className="font-bold">$357.5M</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Post-Series C (62%)</span>
                      <span className="font-bold">$1.3B</span>
                    </div>
                    <div className="flex justify-between text-green-400">
                      <span>IPO (55%)</span>
                      <span className="font-bold">$2.31B</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-purple-900 to-blue-900 rounded-lg p-6 text-center">
                <p className="text-gray-300 mb-2">Year 3 Milestone</p>
                <p className="text-4xl font-bold text-white mb-2">🦄 UNICORN STATUS</p>
                <p className="text-xl text-purple-300">$966M - $1.2B Valuation</p>
              </div>
            </div>
          )}
        </div>

        {/* Footer Summary */}
        <div className="mt-8 bg-gradient-to-r from-gray-800 to-gray-900 rounded-xl p-6">
          <h3 className="text-xl font-semibold mb-4">5-Year Summary</h3>
          <div className="grid md:grid-cols-5 gap-4 text-center text-sm">
            <div>
              <p className="text-gray-400">Cumulative Revenue</p>
              <p className="text-2xl font-bold">$732M</p>
            </div>
            <div>
              <p className="text-gray-400">Cumulative Net Income</p>
              <p className="text-2xl font-bold text-green-400">$415M</p>
            </div>
            <div>
              <p className="text-gray-400">Cards Pre-Graded</p>
              <p className="text-2xl font-bold text-amber-400">60.5M</p>
            </div>
            <div>
              <p className="text-gray-400">Total Customers</p>
              <p className="text-2xl font-bold text-blue-400">2.01M</p>
            </div>
            <div>
              <p className="text-gray-400">Final Valuation</p>
              <p className="text-2xl font-bold text-purple-400">$4.5B</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
