using System.Globalization;
using System.Windows.Data;
using System.Windows.Media;

namespace TradeAtlas.Converters;

public class PnlToColorConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        if (value is double pnl)
        {
            if (pnl > 0) return Brushes.Green;
            if (pnl < 0) return Brushes.Red;
        }
        return Brushes.Gray;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
    {
        throw new NotSupportedException();
    }
}
