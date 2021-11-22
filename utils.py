# import packages
import base64
import io

# dashboard
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import pandas as pd
from collections import OrderedDict
import plotly.graph_objs as go
import dash_bootstrap_components as dbc

# API
import requests
import json

# calculations
import math


class Backend:
    """
    In this section, static variables will be initiated.
    """

    # template for API POST for the sizer
    # quick
    json_template_quick_post = {
        "globalSpecs": {},
        "workloads": [
            {
                "profileName": "Workload Profile - 1",
                "vmProfile": {
                    "vCpusPerCore": 4,
                    "vCpusPerVM": 2,
                    "vRAMPerVM": {
                        "value": 200
                    },
                    "vmdkSize": {
                        "value": 200
                    },
                    "vmsNum": 1000
                },
                "workloadType": "GPW_GVM"
            }
        ]
    }

    # manual
    # todo

    # initiate as None row 3 that contains search VMs based on ram and storage usage
    row_3 = None

    def __init__(self):
        """
        This function initiates the backend class dealing with all the sizer options.
        The initiation happens when an Rvtools is added to the dashboard and takes the elements to read it as inputs.

        -----------------------------------
        Initialised variables:

        :var - contents:  base64 encoded string
        Parameter from the dcc.Upload object that contains the files contents.

        :var - filename: string
        The name of the file(s) that was(were) uploaded. Note that this does not include the path of the file
        (for security reasons).

        #todo: rest of variables annotations
        """

        # rvtools file information
        self.filename, self.contents = [None] * 2

        # class variables to share the opened databases (entire scope)
        self.vinfo, self.vpartition, self.vmemory = [None] * 3
        self.vinfo_provisioned, self.vpartition_provisioned, self.vmemory_provisioned = [None] * 3
        self.vinfo_used, self.vpartition_used, self.vmemory_used = [None] * 3
        self.vinfo_consumed, self.vpartition_consumed, self.vmemory_consumed = [None] * 3

        # class variables to share the opened databases (removed scope)
        self.vinfo_removed_used, self.vpartition_removed_used, self.vmemory_removed_used = [None] * 3
        self.vinfo_removed_provisioned, self.vpartition_removed_provisioned, \
        self.vmemory_removed_provisioned = [None] * 3
        self.vinfo_removed_consumed, self.vpartition_removed_consumed, self.vmemory_removed_consumed = [None] * 3

        # initiate dictionary where all important values will be stored
        self.value_dict_provisioned = dict()
        self.value_dict_used = dict()
        self.value_dict_consumed = dict()

        # class variables to keep track of scope
        # List of string names of VMs removed from scope
        self.removed_vms_consumed = list()
        self.removed_vms_provisioned = list()
        self.removed_vms_used = list()

        # Variable setting if powered off VMs should be removed
        self.pow_off = [None]

    def open_rvtools(self):
        """
        Function to open the rvtools fed to the upload object in the dashboard.
        """

        content_type, content_string = self.contents[0].split(',')

        #content_string = parse_contents(self.contents)

        decoded = base64.b64decode(content_string)

        self.vinfo = pd.read_excel(io.BytesIO(decoded), "vInfo")
        self.vpartition = pd.read_excel(io.BytesIO(decoded), "vPartition")
        self.vmemory = pd.read_excel(io.BytesIO(decoded), "vMemory")

    def create_rvtools_table(self, title, vinfo, vmemory, vpartition):
        """
        Function that uses the class variable databases to create the html Div displaying the Rvtools.

        :return: html.Div
        The application display for the datatable.
        """
        return html.Div([
            html.H5(title),

            dcc.Tabs([
                dcc.Tab(label='vInfo', children=[
                    dash_table.DataTable(
                        data=vinfo.to_dict('records'),
                        columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                 vinfo.columns],
                        style_cell={'textAlign': 'left'},
                        style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                        filter_action="native",
                        sort_action="native",
                        sort_mode="multi",
                        # row_selectable="multi",
                        # row_deletable=True,
                        # selected_columns=[],
                        # selected_rows=[]
                    )
                ]),
                dcc.Tab(label='vMemory', children=[
                    dash_table.DataTable(
                        data=vmemory.to_dict('records'),
                        columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                 vmemory.columns],
                        style_cell={'textAlign': 'left'},
                        style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                        filter_action="native",
                        sort_action="native",
                        sort_mode="multi",
                        # row_selectable="multi",
                        # row_deletable=True,
                        # selected_columns=[],
                        # selected_rows=[]
                    )
                ]),
                dcc.Tab(label='vPartition', children=[
                    dash_table.DataTable(
                        data=vpartition.to_dict('records'),
                        columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                 vpartition.columns],
                        style_cell={'textAlign': 'left'},
                        style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                        filter_action="native",
                        sort_action="native",
                        sort_mode="multi",
                        # row_selectable="multi",
                        # row_deletable=True,
                        # selected_columns=[],
                        # selected_rows=[]
                    )
                ])
            ]),

        ])

    def vinfo_summary(self):
        """
        Main function doing the calculations, research and preparing of datasets for display on dashboard.
        # todo make this more efficient, neat and compartmentalized.

        :output: dict
        Formated dictionary with all values of interest to display on dashboard
        """
        # initiate function helper variable

        # temporary variable to add "in use (MB)" storage value from vInfo for VMs not running as they will not appear
        # in the vPartition tab
        temp_sto = 0

        # get number of VMs with "Powerstate" values
        temp = self.vinfo["Powerstate"].unique()
        if "poweredOn" in temp and "poweredOff" in temp:
            vm_off = self.vinfo["Powerstate"].value_counts()["poweredOff"]
        elif "poweredOff" in temp:
            vm_off = self.vinfo["Powerstate"].value_counts()["poweredOff"]
        else:
            vm_off = 0

        # remove VMs not running or poweroff if necessary & if not store In Use storage to use in consumed sizing as
        # VMs powered off dont appear in vpartition
        if self.pow_off == "yes":
            self.vinfo = self.vinfo[self.vinfo["Powerstate"] != "poweredOff"]
            self.vpartition = self.vinfo[self.vpartition["Powerstate"] != "poweredOff"]
            self.vmemory = self.vinfo[self.vmemory["Powerstate"] != "poweredOff"]
        else:
            # todo: make sure they dont actually exist in vPartition already
            temp_sto += self.vinfo[self.vinfo["Powerstate"] == "poweredOff"]["In Use MB"].sum()

        # Create a database for VMs removed from scope
        self.vinfo_removed_provisioned = self.vinfo[self.vinfo['VM'].isin(self.removed_vms_provisioned)]
        self.vpartition_removed_provisioned = self.vpartition[self.vpartition['VM'].isin(self.removed_vms_provisioned)]
        self.vmemory_removed_provisioned = self.vmemory[self.vmemory['VM'].isin(self.removed_vms_provisioned)]

        # create dbs for the scoepd vm in each metrics
        self.vinfo_provisioned = self.vinfo[~self.vinfo['VM'].isin(self.removed_vms_provisioned)]
        self.vpartition_provisioned = self.vpartition[~self.vpartition['VM'].isin(self.removed_vms_provisioned)]
        self.vmemory_provisioned = self.vmemory[~self.vmemory['VM'].isin(self.removed_vms_provisioned)]

        self.vinfo_used = self.vinfo[~self.vinfo['VM'].isin(self.removed_vms_used)]
        self.vpartition_used = self.vpartition[~self.vpartition['VM'].isin(self.removed_vms_used)]
        self.vmemory_used = self.vmemory[~self.vmemory['VM'].isin(self.removed_vms_used)]

        self.vinfo_consumed = self.vinfo[~self.vinfo['VM'].isin(self.removed_vms_consumed)]
        self.vpartition_consumed = self.vpartition[~self.vpartition['VM'].isin(self.removed_vms_consumed)]
        self.vmemory_consumed = self.vmemory[~self.vmemory['VM'].isin(self.removed_vms_consumed)]

        # get storage in GiB & add In Use for VMs that dont have VM Tools (not in vPartition)
        consumed_sto = (self.vpartition_consumed["Consumed MB"].sum() + temp_sto) / 1024
        consumed_sto += self.vinfo_consumed[~self.vinfo_consumed['VM'].isin(self.vpartition_consumed['VM'])][
                            'In Use MB'].sum() / 1024

        # aggregate results for test
        self.value_dict_provisioned = {"VM(s)": self.vinfo_provisioned.shape[0],
                                       "CPU(s)": self.vinfo_provisioned.CPUs.sum(),
                                       "RAM GiB": self.vinfo_provisioned.Memory.sum() / 1024,
                                       "Storage GiB": self.vinfo_provisioned['Provisioned MB'].sum() / 1024,
                                       "rcpu": math.ceil(
                                           self.vinfo_provisioned.CPUs.sum() / self.vinfo_provisioned.shape[0]),
                                       "rram": math.ceil(
                                           (self.vinfo_provisioned.Memory.sum() / 1024) / self.vinfo_provisioned.shape[
                                               0]),
                                       "rsto": math.ceil(
                                           (self.vinfo_provisioned['Provisioned MB'].sum() / 1024) /
                                           self.vinfo_provisioned.shape[0]),
                                       "VM poweredOff": vm_off}

        # aggregate results for test
        self.value_dict_used = {"VM(s)": self.vinfo_used.shape[0],
                                "CPU(s)": self.vinfo_used.CPUs.sum(),
                                "RAM GiB": self.vmemory_used.Consumed.sum() / 1024,
                                "Storage GiB": self.vinfo_used['In Use MB'].sum() / 1024,
                                "rcpu": math.ceil(self.vinfo_used.CPUs.sum() / self.vinfo_used.shape[0]),
                                "rram": math.ceil(
                                    (self.vmemory_used.Consumed.sum() / 1024) / self.vinfo_used.shape[0]),
                                "rsto": math.ceil(
                                    (self.vinfo_used['In Use MB'].sum() / 1024) / self.vinfo_used.shape[0]),
                                "VM poweredOff": vm_off}

        # aggregate results for test
        self.value_dict_consumed = {"VM(s)": self.vinfo_consumed.shape[0],
                                    "CPU(s)": self.vinfo_consumed.CPUs.sum(),
                                    "RAM GiB": self.vmemory_consumed.Consumed.sum() / 1024,
                                    "Storage GiB": consumed_sto,
                                    "rcpu": math.ceil(self.vinfo_consumed.CPUs.sum() / self.vinfo_consumed.shape[0]),
                                    "rram": math.ceil(
                                        (self.vmemory_consumed.Consumed.sum() / 1024) / self.vinfo_consumed.shape[0]),
                                    "rsto": math.ceil(consumed_sto / self.vinfo_consumed.shape[0]),
                                    "VM poweredOff": vm_off}

    def get_api_response(self, values):
        # initialise POST with template
        post = self.json_template_quick_post

        # set values
        post['workloads'][0]['vmProfile']['vCpusPerVM'] = values[1]
        post['workloads'][0]['vmProfile']['vRAMPerVM']['value'] = values[2]
        post['workloads'][0]['vmProfile']['vmdkSize']['value'] = values[3]
        post['workloads'][0]['vmProfile']['vmsNum'] = values[0]

        headers = {'content-type': 'application/json'}
        response = requests.post("https://vmc.vmware.com/api/sizer/v4/recommendation?cloudProviderType=VMC_ON_AWS",
                                 json=post, headers=headers)

        return json.loads(response.text)['genericResponse']

    def get_sizer_info(self):

        # call function to gather data to display
        self.vinfo_summary()

        # arrange for sizer metrics
        sizer_table_data_provisioned = pd.DataFrame(OrderedDict([
            ('units', ['VM(s)', 'CPU(s)', 'RAM (GiB)', 'Storage (Gib)']),
            ('values', [self.value_dict_provisioned[i] for i in ["VM(s)", "CPU(s)", "RAM GiB", "Storage GiB"]])
        ]))
        sizer_table_data_provisioned_rounded = pd.DataFrame(OrderedDict([
            ('units', ['VM(s)', 'CPU(s)', 'RAM (GiB)', 'Storage (Gib)']),
            ('values', [self.value_dict_provisioned[i] for i in ["VM(s)", "rcpu", "rram", "rsto"]])
        ]))

        sizer_table_data_used = pd.DataFrame(OrderedDict([
            ('units', ['VM(s)', 'CPU(s)', 'RAM (GiB)', 'Storage (Gib)']),
            ('values', [self.value_dict_used[i] for i in ["VM(s)", "CPU(s)", "RAM GiB", "Storage GiB"]])
        ]))
        sizer_table_data_used_rounded = pd.DataFrame(OrderedDict([
            ('units', ['VM(s)', 'CPU(s)', 'RAM (GiB)', 'Storage (Gib)']),
            ('values', [self.value_dict_used[i] for i in ["VM(s)", "rcpu", "rram", "rsto"]])
        ]))

        sizer_table_data_consumed = pd.DataFrame(OrderedDict([
            ('units', ['VM(s)', 'CPU(s)', 'RAM (GiB)', 'Storage (Gib)']),
            ('values', [self.value_dict_consumed[i] for i in ["VM(s)", "CPU(s)", "RAM GiB", "Storage GiB"]])
        ]))
        sizer_table_data_consumed_rounded = pd.DataFrame(OrderedDict([
            ('units', ['VM(s)', 'CPU(s)', 'RAM (GiB)', 'Storage (Gib)']),
            ('values', [self.value_dict_consumed[i] for i in ["VM(s)", "rcpu", "rram", "rsto"]])
        ]))

        # get response dictionary
        out_gen_provisioned = self.get_api_response(
            [self.value_dict_provisioned[i] for i in ["VM(s)", "rcpu", "rram", "rsto"]])
        out_gen_consumed = self.get_api_response(
            [self.value_dict_consumed[i] for i in ["VM(s)", "rcpu", "rram", "rsto"]])
        out_gen_used = self.get_api_response(
            [self.value_dict_used[i] for i in ["VM(s)", "rcpu", "rram", "rsto"]])

        # arrange sizer metrics & graphs
        temp_units_to_display = ['I3 Host Count', 'Total Cores', 'Total Memory', 'Total Storage', 'FTT & FTM']
        sized_table_data_provisioned = pd.DataFrame(OrderedDict([
            ('units', temp_units_to_display),
            ('values', [out_gen_provisioned['sddcInformation']['nodesSize'],
                        out_gen_provisioned['sddcInformation']['provisionedCores'],
                        out_gen_provisioned['sddcInformation']['provisionedMemory']['value'],
                        out_gen_provisioned['sddcInformation']['provisionedStorage']['value'],
                        out_gen_provisioned['sddcInformation']['fttAndftm']])
        ]))

        x_data_provisioned = [
            [out_gen_provisioned['cpuCoresUsage']['consumed'], out_gen_provisioned['cpuCoresUsage']['free']],
            [out_gen_provisioned['memoryUsage']['consumed']['value'],
             out_gen_provisioned['memoryUsage']['free']['value']],
            [out_gen_provisioned['diskSpaceUsage']['consumedStorage']['value'],
             out_gen_provisioned['diskSpaceUsage']['consumedSystemStorage']['value'],
             out_gen_provisioned['diskSpaceUsage']['freeStorage']['value']]]

        sized_table_data_used = pd.DataFrame(OrderedDict([
            ('units', temp_units_to_display),
            ('values',
             [out_gen_used['sddcInformation']['nodesSize'], out_gen_used['sddcInformation']['provisionedCores'],
              out_gen_used['sddcInformation']['provisionedMemory']['value'],
              out_gen_used['sddcInformation']['provisionedStorage']['value'],
              out_gen_used['sddcInformation']['fttAndftm']])
        ]))

        x_data_used = [[out_gen_used['cpuCoresUsage']['consumed'], out_gen_used['cpuCoresUsage']['free']],
                       [out_gen_used['memoryUsage']['consumed']['value'], out_gen_used['memoryUsage']['free']['value']],
                       [out_gen_used['diskSpaceUsage']['consumedStorage']['value'],
                        out_gen_used['diskSpaceUsage']['consumedSystemStorage']['value'],
                        out_gen_used['diskSpaceUsage']['freeStorage']['value']]]

        sized_table_data_consumed = pd.DataFrame(OrderedDict([
            ('units', temp_units_to_display),
            ('values',
             [out_gen_consumed['sddcInformation']['nodesSize'], out_gen_consumed['sddcInformation']['provisionedCores'],
              out_gen_consumed['sddcInformation']['provisionedMemory']['value'],
              out_gen_consumed['sddcInformation']['provisionedStorage']['value'],
              out_gen_consumed['sddcInformation']['fttAndftm']])
        ]))

        x_data_consumed = [[out_gen_consumed['cpuCoresUsage']['consumed'], out_gen_consumed['cpuCoresUsage']['free']],
                           [out_gen_consumed['memoryUsage']['consumed']['value'],
                            out_gen_consumed['memoryUsage']['free']['value']],
                           [out_gen_consumed['diskSpaceUsage']['consumedStorage']['value'],
                            out_gen_consumed['diskSpaceUsage']['consumedSystemStorage']['value'],
                            out_gen_consumed['diskSpaceUsage']['freeStorage']['value']]]

        rvtools_provisioned = self.create_rvtools_table("Provisioned Scope RvTools", self.vinfo_provisioned,
                                                        self.vmemory_provisioned, self.vpartition_provisioned)
        rvtools_used = self.create_rvtools_table("Used Scope RvTools", self.vinfo_used,
                                                 self.vmemory_used, self.vpartition_used)
        rvtools_consumed = self.create_rvtools_table("Consumed Scope RvTools", self.vinfo_consumed,
                                                     self.vmemory_consumed, self.vpartition_consumed)
        # input values into dash objects to display

        return html.Div([
            dcc.Tabs([
                dcc.Tab(label="provisioned", children=[
                    rvtools_provisioned,
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizing Metrics Total"], className="subtitle padded"
                                    ),

                                    dash_table.DataTable(
                                        data=sizer_table_data_provisioned.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]), style={"height": "100%"},
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizing Metrics Rounded"], className="subtitle padded"
                                    ),
                                    dash_table.DataTable(
                                        data=sizer_table_data_provisioned_rounded.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]),
                                style={"height": "100%"},
                            )
                        ]
                    ),
                    html.Br(),
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizer Metrics Provisioned"], className="subtitle padded"
                                    ),
                                    html.I(
                                        "This sizing was made based on the rounded up per VM values of the CPU, \
                                        Memory and Provisioned MB columns of vInfo."
                                    ),
                                    dash_table.DataTable(
                                        data=sized_table_data_provisioned.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Cores"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(
                                        figure=go.Figure(
                                            data=go.Pie(labels=['Consumed', 'Free'], values=x_data_provisioned[0]),
                                            layout={}))

                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Memory"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(
                                        figure=go.Figure(
                                            data=go.Pie(labels=['Consumed', 'Free'], values=x_data_provisioned[1]),
                                            layout={}))

                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Storage"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(figure=go.Figure(
                                        data=go.Pie(labels=['Consumed by workloads', 'Consumed by system', 'Free'],
                                                    values=x_data_provisioned[2]),
                                        layout={})
                                    )
                                ]),
                            )
                        ]
                    ),
                    html.Br(),
                    html.Div([
                        html.H5('VM(s) Removed from Provisioned Scope'),

                        dcc.Tabs([
                            dcc.Tab(label='vInfo', children=[
                                dash_table.DataTable(
                                    data=self.vinfo_removed_provisioned.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vinfo_removed_provisioned.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ]),
                            dcc.Tab(label='vMemory', children=[
                                dash_table.DataTable(
                                    data=self.vmemory_removed_provisioned.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vmemory_removed_provisioned.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ]),
                            dcc.Tab(label='vPartition', children=[
                                dash_table.DataTable(
                                    data=self.vpartition_removed_provisioned.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vpartition_removed_provisioned.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ])
                        ])
                    ])
                ]),
                dcc.Tab(label="used", children=[
                    rvtools_used,
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizing Metrics Total"], className="subtitle padded"
                                    ),

                                    dash_table.DataTable(
                                        data=sizer_table_data_used.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]), style={"height": "100%"},
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizing Metrics Rounded"], className="subtitle padded"
                                    ),
                                    dash_table.DataTable(
                                        data=sizer_table_data_used_rounded.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]),
                                style={"height": "100%"},
                            )
                        ]
                    ),
                    html.Br(),
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizer Metrics Used"], className="subtitle padded"
                                    ),
                                    html.I(
                                        "This sizing was made based on the rounded up per VM values of the CPU and In \
                                        Use MB columns of vInfo and the Consumed column from vMemory. "
                                    ),
                                    dash_table.DataTable(
                                        data=sized_table_data_used.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Cores"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(
                                        figure=go.Figure(
                                            data=go.Pie(labels=['Consumed', 'Free'], values=x_data_used[0]),
                                            layout={}))

                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Memory"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(
                                        figure=go.Figure(
                                            data=go.Pie(labels=['Consumed', 'Free'], values=x_data_used[1]),
                                            layout={}))

                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Storage"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(figure=go.Figure(
                                        data=go.Pie(labels=['Consumed by workloads', 'Consumed by system', 'Free'],
                                                    values=x_data_used[2]),
                                        layout={})
                                    )
                                ]),
                            )
                        ]
                    ),
                    html.Br(),
                    html.Div([
                        html.H5('VM(s) Removed from Used Scope'),

                        dcc.Tabs([
                            dcc.Tab(label='vInfo', children=[
                                dash_table.DataTable(
                                    data=self.vinfo_removed_used.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vinfo_removed_used.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ]),
                            dcc.Tab(label='vMemory', children=[
                                dash_table.DataTable(
                                    data=self.vmemory_removed_used.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vmemory_removed_used.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ]),
                            dcc.Tab(label='vPartition', children=[
                                dash_table.DataTable(
                                    data=self.vpartition_removed_used.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vpartition_removed_used.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ])
                        ])
                    ])
                ]),
                dcc.Tab(label="consumed", children=[
                    rvtools_consumed,
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizing Metrics Total"], className="subtitle padded"
                                    ),

                                    dash_table.DataTable(
                                        data=sizer_table_data_consumed.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]), style={"height": "100%"},
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizing Metrics Rounded"], className="subtitle padded"
                                    ),
                                    dash_table.DataTable(
                                        data=sizer_table_data_consumed_rounded.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]),
                                style={"height": "100%"},
                            )
                        ]
                    ),
                    html.Br(),
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Sizer Metrics Consumed"], className="subtitle padded"
                                    ),
                                    html.I(
                                        "This sizing was made based on the rounded up per VM values of the CPU column \
                                        in vInfo, the Consumed column in vMemory and the Consumed MB in vPartition."
                                    ),
                                    dash_table.DataTable(
                                        data=sized_table_data_consumed.to_dict('records'),
                                        columns=[{
                                            'id': 'units',
                                            'name': 'Unit',
                                            'type': 'text'
                                        }, {
                                            'id': 'values',
                                            'name': 'Value',
                                            'type': 'numeric'
                                        }],
                                        style_cell={'textAlign': 'left', 'padding': '5px'},
                                        style_table={'height': 'auto', "width": 'auto', 'overflowY': 'auto',
                                                     'overflowX': 'auto'},
                                        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': c},
                                                'textAlign': 'center'
                                            } for c in ['Value']
                                        ],
                                    )
                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Cores"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(
                                        figure=go.Figure(
                                            data=go.Pie(labels=['Consumed', 'Free'], values=x_data_consumed[0]),
                                            layout={}))

                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Memory"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(
                                        figure=go.Figure(
                                            data=go.Pie(labels=['Consumed', 'Free'], values=x_data_consumed[1]),
                                            layout={}))

                                ]),
                            ),
                            dbc.Col(
                                html.Div([
                                    html.H5(
                                        ["Total Storage"], className="subtitle padded"
                                    ),

                                    # VMware license table
                                    # tab VMware VM's ??
                                    dcc.Graph(figure=go.Figure(
                                        data=go.Pie(labels=['Consumed by workloads', 'Consumed by system', 'Free'],
                                                    values=x_data_consumed[2]),
                                        layout={})
                                    )
                                ]),
                            )
                        ]
                    ),
                    html.Br(),
                    html.Div([
                        html.H5('VM(s) Removed from Consumed Scope'),

                        dcc.Tabs([
                            dcc.Tab(label='vInfo', children=[
                                dash_table.DataTable(
                                    data=self.vinfo_removed_consumed.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vinfo_removed_consumed.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ]),
                            dcc.Tab(label='vMemory', children=[
                                dash_table.DataTable(
                                    data=self.vmemory_removed_consumed.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vmemory_removed_consumed.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ]),
                            dcc.Tab(label='vPartition', children=[
                                dash_table.DataTable(
                                    data=self.vpartition_removed_consumed.to_dict('records'),
                                    columns=[{'name': i, 'id': i, "deletable": False, "selectable": False} for i in
                                             self.vpartition_removed_consumed.columns],
                                    style_cell={'textAlign': 'left'},
                                    style_table={'height': '300px', 'overflowY': 'auto', 'overflowX': 'auto'},
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                    # row_selectable="multi",
                                    # row_deletable=True,
                                    # selected_columns=[],
                                    # selected_rows=[]
                                )
                            ])
                        ])
                    ])
                ]),
            ])
        ])
