# To add a new cell, type '#%%'
# To add a new markdown cell, type '#%% [markdown]'
#%% Change working directory from the workspace root to the ipynb file location. Turn this addition off with the DataScience.changeDirOnImportExport setting
# ms-python.python added
import os
try:
	os.chdir(os.path.join(os.getcwd(), 'assessment'))
	print(os.getcwd())
except:
	pass
#%%
from IPython import get_ipython

#%% [markdown]
# ### *IPCC SR15 scenario assessment*
# 
# <img style="float: right; height: 80px; padding-left: 20px;" src="../_static/IIASA_logo.png">
# <img style="float: right; height: 80px;" src="../_static/IAMC_logo.jpg">
# 
# # Characteristics of four illustrative model pathways
# ## Figure 3b of the *Summary for Policymakers*
# 
# This notebook derives the indicators for the table in Figure 3b in the Summary for Policymakers
# of the IPCC's _"Special Report on Global Warming of 1.5°C"_.
# 
# The scenario data used in this analysis can be accessed and downloaded at [https://data.ene.iiasa.ac.at/iamc-1.5c-explorer](https://data.ene.iiasa.ac.at/iamc-1.5c-explorer).
#%% [markdown]
# ## Load `pyam` package and other dependencies

#%%
import pandas as pd
import numpy as np
import warnings
import io
import itertools
import yaml
import math
import matplotlib.pyplot as plt
plt.style.use('style_sr15.mplstyle')
get_ipython().run_line_magic('matplotlib', 'inline')
import pyam

#%% [markdown]
# ## Import scenario data, categorization and specifications files
# 
# The metadata file must be generated from the notebook `sr15_2.0_categories_indicators` included in this repository.  
# If the snapshot file has been updated, make sure that you rerun the categorization notebook.
# 
# The last cell of this section loads and assigns a number of auxiliary lists as defined in the categorization notebook.

#%%
sr1p5 = pyam.IamDataFrame(data='../data/iamc15_scenario_data_world_r1.1.xlsx')


#%%
sr1p5.load_metadata('sr15_metadata_indicators.xlsx')


#%%
with open("sr15_specs.yaml", 'r') as stream:
    specs = yaml.load(stream, Loader=yaml.FullLoader)

rc = pyam.run_control()
for item in specs.pop('run_control').items():
    rc.update({item[0]: item[1]})
cats_15 = specs.pop('cats_15')
cats_15_no_lo = specs.pop('cats_15_no_lo')
marker = specs.pop('marker')

#%% [markdown]
# ## Downselect scenario ensemble to categories of interest for this assessment

#%%
sr1p5.meta.rename(columns={'Kyoto-GHG|2010 (SAR)': 'kyoto_ghg_2010'}, inplace=True)


#%%
df = sr1p5.filter(category=cats_15)


#%%
base_year = 2010
compare_years = [2030, 2050]
years = [base_year] + compare_years

#%% [markdown]
# ## Initialize a `pyam.Statistics` instance

#%%
stats = pyam.Statistics(df=df, groupby={'marker': ['LED', 'S1', 'S2', 'S5']},
                        filters=[(('pathways', 'no & lo os 1.5'), {'category': cats_15_no_lo})])

#%% [markdown]
# ## Collecting indicators
# 
# ### CO2 and Kyoto GHG emissions reductions

#%%
co2 = (
    df.filter(kyoto_ghg_2010='in range', variable='Emissions|CO2', year=years)
    .convert_unit({'Mt CO2/yr': ('Gt CO2/yr', 0.001)})
    .timeseries()
)


#%%
for y in compare_years:
    stats.add((co2[y] / co2[2010] - 1) * 100,
        'CO2 emission reduction (% relative to 2010)',
        subheader=y)


#%%
kyoto_ghg = (
    df.filter(kyoto_ghg_2010='in range', variable='Emissions|Kyoto Gases (SAR-GWP100)', year=years)
    .convert_unit({'Mt CO2-equiv/yr': ('Gt CO2-equiv/yr', 0.001)})
    .timeseries()
)
for y in compare_years:
    stats.add((kyoto_ghg[y] / kyoto_ghg[base_year] - 1) * 100,
        'Kyoto-GHG emission reduction (SAR-GWP100), % relative to {})'.format(base_year),
        subheader=y)

#%% [markdown]
# ### Final energy demand reduction relative to 2010

#%%
fe = df.filter(variable='Final Energy', year=years).timeseries()
for y in compare_years:
    stats.add((fe[y] / fe[base_year] - 1) * 100,
              'Final energy demand reduction relative to {} (%)'.format(base_year),
              subheader=y)

#%% [markdown]
# ### Share of renewables in electricity generation

#%%
def add_stats_share(stats, var_list, name, total, total_name, years, df=df):

    _df = df.filter(variable=var_list)
    for v in var_list:
        _df.require_variable(v, exclude_on_fail=True)
    _df.filter(exclude=False, inplace=True)

    component = (
        _df.timeseries()
        .groupby(['model', 'scenario']).sum()
    )
    share = component / total * 100
    
    for y in years:
        stats.add(share[y], header='Share of {} in {} (%)'.format(name, total_name),
                  subheader=y)


#%%
ele = df.filter(variable='Secondary Energy|Electricity', year=compare_years).timeseries()
ele.index = ele.index.droplevel([2, 3, 4])


#%%
ele_re_vars = [
    'Secondary Energy|Electricity|Biomass',
    'Secondary Energy|Electricity|Non-Biomass Renewables'
]
add_stats_share(stats, ele_re_vars, 'renewables', ele, 'electricity', compare_years)

#%% [markdown]
# ### Changes in primary energy mix

#%%
mapping = [
    ('coal', 'Coal'),
    ('oil', 'Oil'),
    ('gas', 'Gas'),
    ('nuclear', 'Nuclear'),
    ('bioenergy', 'Biomass'),
    ('non-biomass renewables', 'Non-Biomass Renewables')
]


#%%
for (n, v) in mapping:
    data = df.filter(variable='Primary Energy|{}'.format(v), year=years).timeseries()

    for y in compare_years:
        stats.add((data[y] / data[base_year] - 1) * 100,
                  header='Primary energy from {} (% rel to {})'.format(n, base_year),
                  subheader=y)

#%% [markdown]
# ###  Cumulative carbon capture and sequestration until the end of the century

#%%
def cumulative_ccs(variable, name, first_year=2016, last_year=2100):

    data = (
        df.filter(variable=variable)
        .convert_unit({'Mt CO2/yr': ('Gt CO2/yr', 0.001)})
        .timeseries()
    )
    
    stats.add(
        data.apply(pyam.cumulative, raw=False, axis=1,
                   first_year=first_year, last_year=last_year),
        header='Cumulative {} until {} (GtCO2)'.format(name, last_year), subheader='')


#%%
cumulative_ccs('Carbon Sequestration|CCS', 'CCS')


#%%
cumulative_ccs('Carbon Sequestration|CCS|Biomass', 'BECCS')

#%% [markdown]
# ### Land cover for energy crops
# 
# Convert unit to SI unit (million square kilometers).

#%%
energy_crops = (
    df.filter(variable='Land Cover|Cropland|Energy Crops', year=2050)
    .convert_unit({'million ha': ('million km2', 0.01)})
    .timeseries()
)


#%%
stats.add(energy_crops[2050], header='Land are for energy crops (million km2)')

#%% [markdown]
# ### Emissions from land use

#%%
species = ['CH4', 'N2O']


#%%
for n in species:
    data = df.filter(kyoto_ghg_2010='in range', variable='Emissions|{}|AFOLU'.format(n), year=years).timeseries()

    for y in compare_years:
        stats.add((data[y] / data[base_year] - 1) * 100,
                  header='Agricultural {} emissions (% rel to {})'.format(n, base_year),
                  subheader=y)

#%% [markdown]
# ## Display summary statistics and export to `xlsx`

#%%
summary = stats.summarize(interquartile=True, custom_format='{:.0f}').T
summary


#%%
summary.to_excel('output/spm_sr15_figure3b_indicators_table.xlsx')


