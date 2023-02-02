"""
API for Cogneato, a tool for experimental optimization.
Optimize expensive, noisy metrics over continuous, categorical, and ordinal parameters.

See:
 https://cogneato.xy
 https://github.com/dsweet99/cogneato-apiz
"""

__version__ = "0.2"

import time
from dataclasses import dataclass

import pandas as pd
import requests


@dataclass
class _CogneatoResponse:
    df_analysis: pd.DataFrame
    df_design: pd.DataFrame
    message: str


def request(df_measurements, number_of_arms, url=None, num_retries=3):
    if url is None:
        url = "https://cogneato.xyz/api"

    df_text = df_measurements.to_json()
    d = {
        "number_of_arms": number_of_arms,
        "measurements": df_text,
    }

    for _ in range(num_retries):
        res = requests.post(url, "", json=d)
        if res.status_code != 200:
            time.sleep(3)
        else:
            break
    else:
        raise Exception(f"Request failed code = {res.status_code}")

    d = res.json()
    if "message" not in d:
        raise Exception(f"Invalid response {d}")
    if d["message"] != "Ok":
        raise Exception(d["message"])
    df_analysis = pd.read_json(d["analysis"])
    df_design = pd.read_json(d["design"])
    return _CogneatoResponse(df_analysis, df_design, d["message"])


class AskTell:
    def __init__(self, param_defs, url=None):
        self._columns = param_defs
        self._url = url
        self._measurements = []
        self._favorite = None
        self._phi_best = -1e99
        self._best = None
        self._num_params = len(self._columns)

    def _mk_param(self, row):
        p = {}
        for i_x, x in enumerate(row.values[: self._num_params]):
            nm, dm = self._columns[i_x].split(":")
            if dm[0] == "[":
                x = float(x)
            elif dm[0] == "{":
                x = int(x)
            p[nm] = x
        return p

    def _clean_design(self, df_design):
        params = []
        for _, row in df_design.iterrows():
            params.append(self._mk_param(row))
        return params

    def favorite(self):
        return self._favorite

    def best(self):
        return self._best

    def ask(self, number_of_arms=1):
        df_measurements = pd.DataFrame(
            columns=self._columns + ["metric:mean", "metric:se"],
            data=self._measurements,
        )
        resp = request(
            df_measurements,
            number_of_arms=number_of_arms,
        )
        if len(resp.df_analysis) > 0:
            row_fav = resp.df_analysis.iloc[0, :]
            self._favorite = (row_fav["metric_est"], self._mk_param(row_fav))
        return self._clean_design(resp.df_design)

    def tell(self, params, phis, ses=None):
        if ses is None:
            ses = ["none"] * len(phis)
        for params, phi, se in zip(params, phis, ses):
            x = [params[k.split(":")[0]] for k in self._columns]
            row = x + [phi, se]
            self._measurements.append(row)
            if phi > self._phi_best:
                self._phi_best = phi
                self._best = (phi, params)
