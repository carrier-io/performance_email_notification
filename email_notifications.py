# Copyright 2019 getcarrier.io

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


class Email(object):
    """
    Email object to store notification details.
    Used by both UI and API email notification generators.
    """

    def __init__(self, test_name, subject, users_to, email_body, charts, date):
        self.test_name = test_name
        self.subject = subject
        self.email_body = email_body
        self.charts = charts
        self.date = date
        self.users_to = users_to
