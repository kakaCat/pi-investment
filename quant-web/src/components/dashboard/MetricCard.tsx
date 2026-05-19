import React from 'react';
import { Card, Statistic, Typography } from 'antd';

const { Text } = Typography;

export interface MetricCardProps {
  title: string;
  value: React.ReactNode;
  suffix?: React.ReactNode;
  prefix?: React.ReactNode;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  loading?: boolean;
  helper?: React.ReactNode;
}

const VALUE_COLORS: Record<NonNullable<MetricCardProps['tone']>, string | undefined> = {
  default: undefined,
  success: '#3f8600',
  warning: '#d48806',
  danger: '#cf1322',
  info: '#1677ff',
};

const bodyStyle: React.CSSProperties = {
  minHeight: 112,
  padding: 16,
};

const helperStyle: React.CSSProperties = {
  display: 'block',
  marginTop: 6,
  minHeight: 22,
};

export default function MetricCard({
  title,
  value,
  suffix,
  prefix,
  tone = 'default',
  loading = false,
  helper,
}: MetricCardProps) {
  return (
    <Card loading={loading} styles={{ body: bodyStyle }}>
      <Statistic
        title={title}
        value={0}
        formatter={() => value}
        prefix={prefix}
        suffix={suffix}
        valueStyle={{ color: VALUE_COLORS[tone], fontSize: 24, lineHeight: 1.25 }}
      />
      {helper ? (
        <Text type="secondary" style={helperStyle}>
          {helper}
        </Text>
      ) : (
        <span style={helperStyle} />
      )}
    </Card>
  );
}
