# import packages

# dahsboard
import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_table

# backend class
from utils import Backend

# Application initial state

# the style arguments for the sidebar.
SIDEBAR_STYLE = {
    'position': 'fixed',
    'top': 0,
    'left': 0,
    'bottom': 0,
    'width': '20%',
    'padding': '20px 10px',
    'background-color': '#f8f9fa',
    'overflowY': 'scroll'
}

# the style arguments for the main content page.
CONTENT_STYLE = {
    'margin-left': '25%',
    'margin-right': '5%',
    'top': 0,
    'padding': '20px 10px'
}

TEXT_STYLE = {
    'textAlign': 'center',
    'color': '#191970'
}
controls = dbc.FormGroup(
    [
        html.P('Upload RVtools Excel', style={
            'textAlign': 'center'
        }),
        dcc.Upload(
            id='upload-data',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select Files')
            ]),
            style={
                'overflowY': 'auto',
                'height': '60px',
                'lineHeight': '60px',
                'borderWidth': '1px',
                'borderStyle': 'dashed',
                'borderRadius': '5px',
                'textAlign': 'center',
                'margin': '10px'
            },
            # Allow multiple files to be uploaded
            # multiple=True
        ),
        html.P(id='file_name'),
        html.P('Exclude VM(s) Prowered Off ?', style={
            'textAlign': 'center'
        }),
        dbc.Card([dbc.Checklist(
            id='exclude_vm',
            options=[{
                'label': 'Yes',
                'value': 'yes'
            },
                {
                    'label': 'No',
                    'value': 'No'
                }
            ],
            value=["yes"],
            inline=True,
            style={
                'margin': 'auto'
            },
        )]),
        html.Br(),
        html.H4('Remove VM(s) by name', style={
            'textAlign': 'center'
        }),
        html.Br(),
        dcc.Dropdown(
            id='out_vm',
            # options=[
            #    {'label': str(i), 'value': str(i)} for i in options
            # ],
            value=[],
            multi=True
        ),
        html.Hr(),
        dbc.Button(
            id='submit_button',
            n_clicks=0,
            children='Submit',
            color='primary',
            block=True
        )
    ],
    style={"height": "100vh"}
)

CARD_TEXT_STYLE = {
    'textAlign': 'center',
    'color': '#0074D9'
}


content_main = html.Div(id='sizer_info')

content = html.Div(
    [
        html.H2('Sizer Automation Prototype', style=TEXT_STYLE),
        html.Hr(),
        content_main
    ],
    style=CONTENT_STYLE
)

sidebar = html.Div(
    [
        html.H2('Parameters', style=TEXT_STYLE),
        html.Hr(),
        controls
    ],
    style=SIDEBAR_STYLE,
)

# create initial dashboard
app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])
app.layout = html.Div([sidebar, content])

# iniate backend class
backend_class = Backend()


@app.callback([Output('file_name', 'children'),
               Output('out_vm', 'options')],
              Input('upload-data', 'contents'),
              State('upload-data', 'filename'))
def update_output1(contents, filename):
    # initiate backend class
    backend_class.contents, backend_class.filename = contents, filename

    if contents is not None:
        backend_class.open_rvtools()

        vm_name = backend_class.vinfo.VM.values
        out2 = [
            {'label': str(i), 'value': str(i)} for i in vm_name
        ]
        return [str(filename), out2]
    else:
        return ['', '']


@app.callback(Output('sizer_info', 'children'),
              Input('submit_button', 'n_clicks'),
              [State('exclude_vm', 'value'),
               State('out_vm', 'value')])
def give_sizing_info(n_clicks, exclude_vm, out_vms):
    if backend_class.contents is not None:
        backend_class.pow_off = exclude_vm
        backend_class.removed_vms_provisioned, backend_class.removed_vms_consumed, \
        backend_class.removed_vms_used = [out_vms] * 3

        return backend_class.get_sizer_info()


app.run_server(debug=False)
