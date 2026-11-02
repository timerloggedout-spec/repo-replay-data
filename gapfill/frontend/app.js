import React from 'react';
import { map, filter } from 'lodash';
import api from 'axios';

function Dashboard() {
  const data = map([1,2,3], x => x * 2);
  return <div>{data}</div>;
}

function Analytics() {
  const filtered = filter([1,2,3,4], n => n > 2);
  return <div>{filtered}</div>;
}

export default Dashboard;